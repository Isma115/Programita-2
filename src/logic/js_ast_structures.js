"use strict";

const fs = require("fs");
const Module = require("module");

function loadNativeModule(id) {
  const source = process.binding("natives")[id];
  if (!source) {
    throw new Error(`Native module not available: ${id}`);
  }

  const mod = new Module(id);
  mod.filename = id;
  mod.paths = Module._nodeModulePaths(process.cwd());
  mod._compile(source, id);
  return mod.exports;
}

const acorn = loadNativeModule("internal/deps/acorn/acorn/dist/acorn");
const amaro = loadNativeModule("internal/deps/amaro/dist/index");

const HOOK_NAMES = new Set(["useEffect", "useLayoutEffect", "useMemo", "useCallback"]);

function readStdin() {
  return fs.readFileSync(0, "utf8");
}

function makePlaceholderPreservingLines(text) {
  if (!text) {
    return text;
  }

  const chars = Array.from(text);
  const out = [];
  const token = ["n", "u", "l", "l"];
  let tokenIndex = 0;

  for (let i = 0; i < chars.length; i += 1) {
    if (chars[i] === "\n") {
      out.push("\n");
      continue;
    }
    out.push(tokenIndex < token.length ? token[tokenIndex] : " ");
    tokenIndex += 1;
  }

  return out.join("");
}

function isIdentifierChar(char) {
  return /[A-Za-z0-9_$]/.test(char || "");
}

function looksLikeJsxStart(source, index) {
  if (source[index] !== "<") {
    return false;
  }

  const next = source[index + 1];
  if (!next || !(/[A-Za-z_]/.test(next) || next === ">")) {
    return false;
  }

  if (next !== ">") {
    let cursor = index + 1;
    while (cursor < source.length && /[A-Za-z0-9_.:$-]/.test(source[cursor])) {
      cursor += 1;
    }
    const afterName = source[cursor];
    if (!(afterName === ">" || afterName === "/" || /\s/.test(afterName || ""))) {
      return false;
    }
  }

  let prev = index - 1;
  while (prev >= 0 && /\s/.test(source[prev])) {
    prev -= 1;
  }
  if (prev < 0) {
    return true;
  }

  const prefix = source.slice(Math.max(0, prev - 24), index);
  if (/(?:return|throw|case|=>)\s*$/.test(prefix)) {
    return true;
  }

  return "([{,:;!?=|&+-*%^~".includes(source[prev]);
}

function skipQuotedString(source, index, quote) {
  let cursor = index + 1;
  while (cursor < source.length) {
    if (source[cursor] === "\\" && cursor + 1 < source.length) {
      cursor += 2;
      continue;
    }
    if (source[cursor] === quote) {
      return cursor + 1;
    }
    cursor += 1;
  }
  return source.length;
}

function consumeTemplateLiteral(source, index) {
  let cursor = index + 1;
  while (cursor < source.length) {
    const char = source[cursor];
    if (char === "\\" && cursor + 1 < source.length) {
      cursor += 2;
      continue;
    }
    if (char === "`") {
      return cursor + 1;
    }
    if (char === "$" && source[cursor + 1] === "{") {
      cursor = consumeJsExpression(source, cursor + 1);
      continue;
    }
    cursor += 1;
  }
  return source.length;
}

function consumeJsExpression(source, index) {
  let cursor = index;
  let depth = 0;

  while (cursor < source.length) {
    const char = source[cursor];
    const next = source[cursor + 1];

    if (char === "'" || char === "\"") {
      cursor = skipQuotedString(source, cursor, char);
      continue;
    }
    if (char === "`") {
      cursor = consumeTemplateLiteral(source, cursor);
      continue;
    }
    if (char === "/" && next === "/") {
      cursor += 2;
      while (cursor < source.length && source[cursor] !== "\n") {
        cursor += 1;
      }
      continue;
    }
    if (char === "/" && next === "*") {
      cursor += 2;
      while (cursor + 1 < source.length && !(source[cursor] === "*" && source[cursor + 1] === "/")) {
        cursor += 1;
      }
      cursor = Math.min(cursor + 2, source.length);
      continue;
    }
    if (char === "<" && looksLikeJsxStart(source, cursor)) {
      const jsxEnd = consumeJsxRegion(source, cursor);
      if (jsxEnd !== null) {
        cursor = jsxEnd;
        continue;
      }
    }
    if (char === "{") {
      depth += 1;
    } else if (char === "}") {
      depth -= 1;
      if (depth <= 0) {
        return cursor + 1;
      }
    }
    cursor += 1;
  }

  return source.length;
}

function readJsxOpenTag(source, index) {
  if (source.startsWith("<>", index)) {
    return { name: "__fragment__", end: index + 2, selfClosing: false };
  }
  if (source[index] !== "<" || source[index + 1] === "/") {
    return null;
  }

  let cursor = index + 1;
  let name = "";
  while (cursor < source.length && /[A-Za-z0-9_.:$-]/.test(source[cursor])) {
    name += source[cursor];
    cursor += 1;
  }
  if (!name) {
    return null;
  }

  let inQuote = null;
  while (cursor < source.length) {
    const char = source[cursor];
    if (inQuote) {
      if (char === "\\" && cursor + 1 < source.length) {
        cursor += 2;
        continue;
      }
      if (char === inQuote) {
        inQuote = null;
      }
      cursor += 1;
      continue;
    }
    if (char === "'" || char === "\"") {
      inQuote = char;
      cursor += 1;
      continue;
    }
    if (char === "{") {
      cursor = consumeJsExpression(source, cursor);
      continue;
    }
    if (char === ">") {
      let back = cursor - 1;
      while (back > index && /\s/.test(source[back])) {
        back -= 1;
      }
      return {
        name,
        end: cursor + 1,
        selfClosing: source[back] === "/",
      };
    }
    cursor += 1;
  }

  return null;
}

function readJsxCloseTag(source, index) {
  if (source.startsWith("</>", index)) {
    return { name: "__fragment__", end: index + 3 };
  }
  if (!source.startsWith("</", index)) {
    return null;
  }

  let cursor = index + 2;
  let name = "";
  while (cursor < source.length && /[A-Za-z0-9_.:$-]/.test(source[cursor])) {
    name += source[cursor];
    cursor += 1;
  }
  if (!name) {
    return null;
  }

  while (cursor < source.length && source[cursor] !== ">") {
    cursor += 1;
  }
  if (cursor >= source.length) {
    return null;
  }
  return { name, end: cursor + 1 };
}

function consumeJsxRegion(source, index) {
  const firstTag = readJsxOpenTag(source, index);
  if (!firstTag) {
    return null;
  }
  if (firstTag.selfClosing) {
    return firstTag.end;
  }

  const stack = [firstTag.name];
  let cursor = firstTag.end;

  while (cursor < source.length) {
    const char = source[cursor];

    if (char === "'" || char === "\"") {
      cursor = skipQuotedString(source, cursor, char);
      continue;
    }
    if (char === "{") {
      cursor = consumeJsExpression(source, cursor);
      continue;
    }
    if (char !== "<") {
      cursor += 1;
      continue;
    }

    const closeTag = readJsxCloseTag(source, cursor);
    if (closeTag) {
      if (stack.length && stack[stack.length - 1] === closeTag.name) {
        stack.pop();
      }
      cursor = closeTag.end;
      if (!stack.length) {
        return cursor;
      }
      continue;
    }

    const openTag = readJsxOpenTag(source, cursor);
    if (!openTag) {
      cursor += 1;
      continue;
    }
    cursor = openTag.end;
    if (!openTag.selfClosing) {
      stack.push(openTag.name);
    }
  }

  return null;
}

function maskJsx(source) {
  const out = [];
  let index = 0;

  while (index < source.length) {
    const char = source[index];
    const next = source[index + 1];

    if (char === "'" || char === "\"") {
      const end = skipQuotedString(source, index, char);
      out.push(source.slice(index, end));
      index = end;
      continue;
    }
    if (char === "`") {
      const end = consumeTemplateLiteral(source, index);
      out.push(source.slice(index, end));
      index = end;
      continue;
    }
    if (char === "/" && next === "/") {
      let end = index + 2;
      while (end < source.length && source[end] !== "\n") {
        end += 1;
      }
      out.push(source.slice(index, end));
      index = end;
      continue;
    }
    if (char === "/" && next === "*") {
      let end = index + 2;
      while (end + 1 < source.length && !(source[end] === "*" && source[end + 1] === "/")) {
        end += 1;
      }
      end = Math.min(end + 2, source.length);
      out.push(source.slice(index, end));
      index = end;
      continue;
    }
    if (char === "<" && looksLikeJsxStart(source, index)) {
      const end = consumeJsxRegion(source, index);
      if (end !== null) {
        out.push(makePlaceholderPreservingLines(source.slice(index, end)));
        index = end;
        continue;
      }
    }

    out.push(char);
    index += 1;
  }

  return out.join("");
}

function preprocessSource(file) {
  let code = file.content || "";
  const ext = file.ext || "";

  if (ext === ".jsx" || ext === ".tsx") {
    code = maskJsx(code);
  }

  if (ext === ".ts" || ext === ".tsx") {
    const transformed = amaro.transformSync(code, { mode: "strip-only" });
    code = transformed.code || transformed;
  }

  return code;
}

function getPropertyName(node) {
  if (!node) {
    return "anonymous";
  }
  if (node.type === "Identifier") {
    return node.name;
  }
  if (node.type === "Literal") {
    return String(node.value);
  }
  if (node.type === "PrivateIdentifier") {
    return node.name;
  }
  return "anonymous";
}

function getHookName(callee) {
  if (!callee) {
    return null;
  }
  if (callee.type === "Identifier" && HOOK_NAMES.has(callee.name)) {
    return callee.name;
  }
  if (
    callee.type === "MemberExpression" &&
    !callee.computed &&
    callee.property &&
    callee.property.type === "Identifier" &&
    HOOK_NAMES.has(callee.property.name)
  ) {
    return callee.property.name;
  }
  return null;
}

function getReturnedJsxStartIndex(returnSource) {
  if (!returnSource) {
    return -1;
  }

  const returnMatch = /\breturn\b/.exec(returnSource);
  if (!returnMatch) {
    return -1;
  }

  let cursor = returnMatch.index + returnMatch[0].length;
  while (cursor < returnSource.length) {
    const char = returnSource[cursor];
    const next = returnSource[cursor + 1];

    if (/\s/.test(char) || char === "(") {
      cursor += 1;
      continue;
    }
    if (char === "/" && next === "/") {
      cursor += 2;
      while (cursor < returnSource.length && returnSource[cursor] !== "\n") {
        cursor += 1;
      }
      continue;
    }
    if (char === "/" && next === "*") {
      cursor += 2;
      while (cursor + 1 < returnSource.length && !(returnSource[cursor] === "*" && returnSource[cursor + 1] === "/")) {
        cursor += 1;
      }
      cursor = Math.min(cursor + 2, returnSource.length);
      continue;
    }
    break;
  }

  for (let index = cursor; index < returnSource.length; index += 1) {
    const char = returnSource[index];
    const next = returnSource[index + 1];

    if (char === "'" || char === "\"") {
      index = skipQuotedString(returnSource, index, char) - 1;
      continue;
    }
    if (char === "`") {
      index = consumeTemplateLiteral(returnSource, index) - 1;
      continue;
    }
    if (char === "/" && next === "/") {
      index += 2;
      while (index < returnSource.length && returnSource[index] !== "\n") {
        index += 1;
      }
      continue;
    }
    if (char === "/" && next === "*") {
      index += 2;
      while (index + 1 < returnSource.length && !(returnSource[index] === "*" && returnSource[index + 1] === "/")) {
        index += 1;
      }
      index = Math.min(index + 1, returnSource.length - 1);
      continue;
    }
    if (char === "<" && looksLikeJsxStart(returnSource, index)) {
      return index;
    }
  }

  return -1;
}

function getJsxReturnDescriptor(node, file) {
  if (!node || node.type !== "ReturnStatement" || !node.loc) {
    return null;
  }
  if (!file || (file.ext !== ".jsx" && file.ext !== ".tsx")) {
    return null;
  }
  if (typeof node.start !== "number" || typeof node.end !== "number") {
    return null;
  }

  const returnSource = (file.content || "").slice(node.start, node.end);
  const jsxIndex = getReturnedJsxStartIndex(returnSource);
  if (jsxIndex === -1) {
    return null;
  }

  const openTag = readJsxOpenTag(returnSource, jsxIndex);
  const jsxLabel = !openTag
    ? "<jsx>"
    : openTag.name === "__fragment__"
      ? "<>"
      : `<${openTag.name}>`;
  const normalizedName = jsxLabel.replace(/[<>]/g, "").replace(/[^\w$.:-]+/g, "_") || "jsx";

  return {
    type: "react_return",
    name: `return_${normalizedName}`,
    display_name: `return (${jsxLabel})`,
    header: `return (${jsxLabel})`,
  };
}

function getStructureDescriptor(node, parent, file) {
  if (!node || !node.loc) {
    return null;
  }

  if (node.type === "FunctionDeclaration" && node.id && node.id.name) {
    return {
      type: "function",
      name: node.id.name,
      display_name: `${node.id.name}()`,
      header: "",
    };
  }

  if (node.type === "ClassDeclaration" && node.id && node.id.name) {
    return {
      type: "class",
      name: node.id.name,
      display_name: node.id.name,
      header: "",
    };
  }

  if (
    node.type === "VariableDeclarator" &&
    node.id &&
    node.id.type === "Identifier" &&
    node.init &&
    (node.init.type === "ArrowFunctionExpression" || node.init.type === "FunctionExpression" || node.init.type === "ClassExpression")
  ) {
    const isClass = node.init.type === "ClassExpression";
    return {
      type: isClass ? "class" : "function",
      name: node.id.name,
      display_name: isClass ? node.id.name : `${node.id.name}()`,
      header: "",
    };
  }

  if (node.type === "MethodDefinition" && node.value && node.value.loc) {
    const methodName = getPropertyName(node.key);
    return {
      type: "method",
      name: methodName,
      display_name: `${methodName}()`,
      header: "",
    };
  }

  if (
    node.type === "PropertyDefinition" &&
    node.key &&
    node.value &&
    (node.value.type === "ArrowFunctionExpression" || node.value.type === "FunctionExpression")
  ) {
    const propertyName = getPropertyName(node.key);
    return {
      type: "method",
      name: propertyName,
      display_name: `${propertyName}()`,
      header: "",
    };
  }

  if (
    node.type === "Property" &&
    parent &&
    parent.type === "ObjectExpression" &&
    node.key &&
    node.value &&
    (node.method || node.value.type === "ArrowFunctionExpression" || node.value.type === "FunctionExpression")
  ) {
    const propertyName = getPropertyName(node.key);
    return {
      type: "method",
      name: propertyName,
      display_name: `${propertyName}()`,
      header: "",
    };
  }

  if (node.type === "ExpressionStatement" && node.expression && node.expression.type === "CallExpression") {
    const hookName = getHookName(node.expression.callee);
    const callback = node.expression.arguments && node.expression.arguments[0];
    if (hookName && callback && (callback.type === "ArrowFunctionExpression" || callback.type === "FunctionExpression")) {
      return {
        type: "function",
        name: hookName,
        display_name: `${hookName}()`,
        header: "",
      };
    }
  }

  const jsxReturnDescriptor = getJsxReturnDescriptor(node, file);
  if (jsxReturnDescriptor) {
    return jsxReturnDescriptor;
  }

  return null;
}

function getChildNodes(node) {
  const children = [];
  for (const key of Object.keys(node || {})) {
    if (key === "loc" || key === "range" || key === "start" || key === "end") {
      continue;
    }
    const value = node[key];
    if (!value) {
      continue;
    }
    if (Array.isArray(value)) {
      for (const item of value) {
        if (item && typeof item.type === "string") {
          children.push(item);
        }
      }
      continue;
    }
    if (value && typeof value.type === "string") {
      children.push(value);
    }
  }
  return children;
}

function buildStructuresForFile(file, astRoot) {
  const results = [];
  const counterByParent = new Map();

  function nextSegment(parentPath, descriptor) {
    const parentKey = parentPath.join("/");
    const counters = counterByParent.get(parentKey) || new Map();
    const base = `${descriptor.type}:${descriptor.name || "anonymous"}`;
    const index = counters.get(base) || 0;
    counters.set(base, index + 1);
    counterByParent.set(parentKey, counters);
    return `${base}[${index}]`;
  }

  function visit(node, parent, parentPath) {
    if (!node || typeof node.type !== "string") {
      return;
    }

    const descriptor = getStructureDescriptor(node, parent, file);
    let currentPath = parentPath;

    if (descriptor) {
      const segment = nextSegment(parentPath, descriptor);
      currentPath = parentPath.concat(segment);
      results.push({
        ...descriptor,
        start_line: node.loc.start.line,
        end_line: node.loc.end.line,
        structure_id: `javascript-ast:${file.rel_path.replace(/\\\\/g, "/")}::${currentPath.join("/")}`,
        parser: "javascript-ast",
      });
    }

    for (const child of getChildNodes(node)) {
      visit(child, node, currentPath);
    }
  }

  visit(astRoot, null, []);
  return results;
}

function parseFile(file) {
  const source = preprocessSource(file);
  const parseOptions = {
    ecmaVersion: "latest",
    sourceType: "module",
    allowHashBang: true,
    locations: true,
  };

  try {
    return acorn.Parser.parse(source, parseOptions);
  } catch (moduleError) {
    try {
      return acorn.Parser.parse(source, { ...parseOptions, sourceType: "script" });
    } catch (scriptError) {
      throw scriptError;
    }
  }
}

function main() {
  const raw = readStdin();
  const files = JSON.parse(raw || "[]");
  const structures = {};
  const errors = {};

  for (const file of files) {
    try {
      const astRoot = parseFile(file);
      structures[file.path] = buildStructuresForFile(file, astRoot);
    } catch (error) {
      errors[file.path] = error && error.message ? error.message : String(error);
      structures[file.path] = [];
    }
  }

  process.stdout.write(JSON.stringify({ structures, errors }));
}

main();
