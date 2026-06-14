#!/usr/bin/env node
'use strict';

/**
 * ast_repair.js — Apply TypeScript AST transformations via ts-morph.
 *
 * Protocol (JSON over stdin/stdout):
 *
 *   Input  (stdin):  { strategy, source, original_code, fixed_code }
 *   Output (stdout): { success, source, changes }         — on success
 *                    { success: false, source, error, changes: 0 }  — on failure
 *
 * Supported strategies:
 *   selector_replace  — replace locator/getByX selector arguments file-wide
 *   import_add        — insert a missing import declaration
 *   timeout_adjust    — update { timeout: N } property values
 *   role_argument     — update the name option in getByRole() calls
 *   assertion_swap    — rename assertion methods in expect() chains
 *
 * The Python caller in src/healing/repair.py falls back to string replacement
 * when success is false or changes === 0.
 */

const { Project, SyntaxKind } = require('ts-morph');

// ── stdin helpers ────────────────────────────────────────────────────────────

function readStdin() {
  return new Promise((resolve, reject) => {
    let data = '';
    process.stdin.setEncoding('utf-8');
    process.stdin.on('data', (chunk) => {
      data += chunk;
    });
    process.stdin.on('end', () => {
      try {
        resolve(JSON.parse(data));
      } catch (e) {
        reject(new Error(`Invalid JSON on stdin: ${e.message}`));
      }
    });
    process.stdin.on('error', reject);
  });
}

function respond(success, source, changes, error) {
  const out = { success, source, changes: changes || 0 };
  if (error) out.error = error;
  process.stdout.write(JSON.stringify(out));
}

// ── string extraction helpers ─────────────────────────────────────────────────

/**
 * Extract the value of the first string literal in a code snippet.
 * Each quote type is matched independently so that the other quote
 * characters may appear inside the string.
 *
 * Examples:
 *   "page.locator('#old')"             → "#old"
 *   "'[data-testid=\"submit\"]'"       → '[data-testid="submit"]'  (single-quoted)
 *   "'[data-testid=\"submit\"]'"       → '[data-testid="submit"]'
 *   "page.getByText('Submit Form')"    → "Submit Form"
 *   "#old"                             → null
 */
function extractFirstStringLiteral(code) {
  // Each pattern matches a properly-closed string of its quote type.
  // The alternation [^'\\] matches any char that is NOT a single-quote or backslash;
  // \\. matches an escape sequence.  Same logic for the other two quote types.
  const patterns = [
    /'((?:[^'\\]|\\.)*)'/, // single-quoted
    /"((?:[^"\\]|\\.)*)"/, // double-quoted
    /`((?:[^`\\]|\\.)*)`/, // backtick
  ];

  let earliest = null;
  for (const pat of patterns) {
    const m = code.match(pat);
    if (m !== null && (earliest === null || m.index < earliest.index)) {
      earliest = m;
    }
  }

  return earliest ? earliest[1] : null;
}

/**
 * Determine which quote character surrounds the selector in fixed_code.
 * Falls back to single quote.
 */
function detectQuoteChar(code) {
  if (!code) return "'";
  const m = code.match(/^[^'"`]*(['"`])/);
  return m ? m[1] : "'";
}

/**
 * Extract the first integer from a code string.
 * "{ timeout: 30000 }" → 30000
 */
function extractFirstInt(code) {
  const m = code.match(/\b(\d+)\b/);
  return m ? parseInt(m[1], 10) : null;
}

/**
 * Extract a method name from a call expression snippet.
 * ".toBe("  → "toBe"
 * "expect(x).toBe("  → "toBe"
 */
function extractLastMethodName(code) {
  const m = code.match(/\.(\w+)\s*\(/g);
  if (!m) return null;
  return m[m.length - 1].replace(/^\.|[\s(]/g, '');
}

// ── strategy implementations ──────────────────────────────────────────────────

/**
 * selector_replace: Find all locator/getByX calls whose first string argument
 * matches original_code (or the selector extracted from it) and replace with
 * the selector from fixed_code.
 */
function selectorReplace(sourceFile, originalCode, fixedCode) {
  const selectorOld = extractFirstStringLiteral(originalCode) || originalCode.trim();
  const selectorNew = extractFirstStringLiteral(fixedCode) || fixedCode.trim();

  if (!selectorOld || !selectorNew) {
    return {
      changes: 0,
      error: 'Could not extract selector values from original_code / fixed_code',
    };
  }

  const LOCATOR_METHODS = new Set([
    'locator',
    'getByText',
    'getByRole',
    'getByLabel',
    'getByPlaceholder',
    'getByTestId',
    'getByTitle',
    'getByAltText',
  ]);

  let changes = 0;
  const quoteChar = detectQuoteChar(fixedCode);

  for (const call of sourceFile.getDescendantsOfKind(SyntaxKind.CallExpression)) {
    const expr = call.getExpression();
    let methodName = null;

    if (expr.getKind() === SyntaxKind.PropertyAccessExpression) {
      methodName = expr.getName();
    } else if (expr.getKind() === SyntaxKind.Identifier) {
      methodName = expr.getText();
    }

    if (!LOCATOR_METHODS.has(methodName)) continue;

    const args = call.getArguments();
    if (args.length === 0) continue;

    const firstArg = args[0];
    if (
      firstArg.getKind() === SyntaxKind.StringLiteral &&
      firstArg.getLiteralValue() === selectorOld
    ) {
      firstArg.replaceWithText(`${quoteChar}${selectorNew}${quoteChar}`);
      changes++;
    }
  }

  return { changes };
}

/**
 * import_add: Parse fixed_code as an import statement and add it to the top of
 * the file. Skips if the module specifier is already imported; merges named
 * imports if the module is partially imported.
 */
function importAdd(sourceFile, _originalCode, fixedCode) {
  const namedMatch = fixedCode.match(/import\s+\{([^}]+)\}\s+from\s+['"`]([^'"`]+)['"`]/);
  const defaultMatch = fixedCode.match(/import\s+(\w+)\s+from\s+['"`]([^'"`]+)['"`]/);
  const sideEffectMatch = fixedCode.match(/import\s+['"`]([^'"`]+)['"`]/);

  if (!namedMatch && !defaultMatch && !sideEffectMatch) {
    return { changes: 0, error: 'Could not parse import statement from fixed_code' };
  }

  const moduleSpecifier = namedMatch
    ? namedMatch[2]
    : defaultMatch
      ? defaultMatch[2]
      : sideEffectMatch[1];

  const existing = sourceFile.getImportDeclaration(moduleSpecifier);

  if (existing && namedMatch) {
    // Module already imported — merge any missing named imports
    const newNames = namedMatch[1]
      .split(',')
      .map((n) => n.trim())
      .filter(Boolean);
    const existingNames = new Set(existing.getNamedImports().map((n) => n.getName()));
    const toAdd = newNames.filter((n) => !existingNames.has(n));
    if (toAdd.length === 0) {
      return { changes: 0, error: 'All named imports already present' };
    }
    for (const name of toAdd) {
      existing.addNamedImport(name);
    }
    return { changes: toAdd.length };
  }

  if (existing) {
    return { changes: 0, error: 'Import already exists' };
  }

  // Insert before the first existing import (or at position 0)
  const imports = sourceFile.getImportDeclarations();
  const insertPos = imports.length > 0 ? 0 : 0;
  sourceFile.insertStatements(insertPos, fixedCode.trim() + '\n');
  return { changes: 1 };
}

/**
 * timeout_adjust: Find all ``{ timeout: N }`` property assignments whose value
 * matches the old timeout and replace with the new timeout.
 */
function timeoutAdjust(sourceFile, originalCode, fixedCode) {
  const oldTimeout = extractFirstInt(originalCode);
  const newTimeout = extractFirstInt(fixedCode);

  if (!oldTimeout || !newTimeout) {
    return { changes: 0, error: 'Could not extract timeout values' };
  }

  let changes = 0;

  for (const prop of sourceFile.getDescendantsOfKind(SyntaxKind.PropertyAssignment)) {
    const nameNode = prop.getNameNode();
    if (!nameNode) continue;

    const propName =
      nameNode.getKind() === SyntaxKind.StringLiteral
        ? nameNode.getLiteralValue()
        : nameNode.getText();

    if (propName !== 'timeout') continue;

    const init = prop.getInitializer();
    if (init && init.getKind() === SyntaxKind.NumericLiteral) {
      if (parseInt(init.getText(), 10) === oldTimeout) {
        init.replaceWithText(String(newTimeout));
        changes++;
      }
    }
  }

  return { changes };
}

/**
 * role_argument: Update the ``name`` option in ``getByRole(role, { name: '...' })``
 * calls where the current name matches the value in original_code.
 */
function roleArgument(sourceFile, originalCode, fixedCode) {
  const oldName = extractFirstStringLiteral(
    originalCode.match(/name:\s*['"`][^'"`]+['"`]/)?.[0] || originalCode
  );
  const newName = extractFirstStringLiteral(
    fixedCode.match(/name:\s*['"`][^'"`]+['"`]/)?.[0] || fixedCode
  );

  if (!oldName || !newName) {
    return { changes: 0, error: 'Could not extract role name values from name: option' };
  }

  const quoteChar = detectQuoteChar(fixedCode.match(/name:\s*(['"`])/)?.[1] ? fixedCode : "'");
  let changes = 0;

  for (const call of sourceFile.getDescendantsOfKind(SyntaxKind.CallExpression)) {
    const expr = call.getExpression();
    if (expr.getKind() !== SyntaxKind.PropertyAccessExpression || expr.getName() !== 'getByRole')
      continue;

    for (const arg of call.getArguments()) {
      if (arg.getKind() !== SyntaxKind.ObjectLiteralExpression) continue;

      for (const prop of arg.getDescendantsOfKind(SyntaxKind.PropertyAssignment)) {
        if (prop.getName() !== 'name') continue;

        const init = prop.getInitializer();
        if (
          init &&
          init.getKind() === SyntaxKind.StringLiteral &&
          init.getLiteralValue() === oldName
        ) {
          init.replaceWithText(`${quoteChar}${newName}${quoteChar}`);
          changes++;
        }
      }
    }
  }

  return { changes };
}

/**
 * assertion_swap: Rename a Playwright/Jest assertion method in expect() chains.
 * e.g. .toBe() → .toEqual()
 */
function assertionSwap(sourceFile, originalCode, fixedCode) {
  const oldMethod = extractLastMethodName(originalCode);
  const newMethod = extractLastMethodName(fixedCode);

  if (!oldMethod || !newMethod) {
    return { changes: 0, error: 'Could not identify assertion method names' };
  }

  let changes = 0;

  for (const prop of sourceFile.getDescendantsOfKind(SyntaxKind.PropertyAccessExpression)) {
    if (prop.getName() !== oldMethod) continue;

    // Confirm it's inside an expect() chain by checking the full expression text
    const text = prop.getText();
    if (!text.includes('expect')) {
      // Walk up to see if it's chained off an expect call
      let parent = prop.getParent();
      let foundExpect = false;
      while (parent) {
        const t = parent.getText();
        if (t.startsWith('expect(') || t.includes('expect(')) {
          foundExpect = true;
          break;
        }
        parent = parent.getParent && parent.getParent();
        if (!parent) break;
      }
      if (!foundExpect) continue;
    }

    prop.getNameNode().replaceWithText(newMethod);
    changes++;
  }

  return { changes };
}

// ── main ─────────────────────────────────────────────────────────────────────

async function main() {
  let input;
  try {
    input = await readStdin();
  } catch (e) {
    respond(false, '', 0, e.message);
    process.exit(1);
  }

  const {
    strategy,
    source = '',
    original_code: originalCode = '',
    fixed_code: fixedCode = '',
  } = input;

  if (!source) {
    respond(false, source, 0, 'source is empty');
    return;
  }

  let project;
  let sourceFile;
  try {
    project = new Project({ useInMemoryFileSystem: true });
    sourceFile = project.createSourceFile('__repair__.spec.ts', source);
  } catch (e) {
    respond(false, source, 0, `Failed to parse source: ${e.message}`);
    return;
  }

  let result;
  try {
    switch (strategy) {
      case 'selector_replace':
        result = selectorReplace(sourceFile, originalCode, fixedCode);
        break;
      case 'import_add':
        result = importAdd(sourceFile, originalCode, fixedCode);
        break;
      case 'timeout_adjust':
        result = timeoutAdjust(sourceFile, originalCode, fixedCode);
        break;
      case 'role_argument':
        result = roleArgument(sourceFile, originalCode, fixedCode);
        break;
      case 'assertion_swap':
        result = assertionSwap(sourceFile, originalCode, fixedCode);
        break;
      default:
        respond(false, source, 0, `Unknown strategy: ${strategy}`);
        return;
    }
  } catch (e) {
    respond(false, source, 0, `Strategy error: ${e.message}`);
    return;
  }

  if (!result || (result.changes === 0 && result.error)) {
    respond(false, source, 0, result ? result.error : 'Unknown error');
    return;
  }

  const modifiedSource = sourceFile.getFullText();
  respond(true, modifiedSource, result.changes || 0, result.error);
}

main().catch((e) => {
  respond(false, '', 0, String(e));
  process.exit(1);
});
