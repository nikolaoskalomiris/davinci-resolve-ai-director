(function () {
    'use strict';

    const ESCAPABLE = /[!"#$%&'()*+,\-./:;<=>?@[\\\]^_`{|}~]/;

    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function safeUrl(value) {
        const trimmed = String(value ?? '').trim();
        return /^(https?:\/\/|mailto:)/i.test(trimmed) ? trimmed : '#';
    }

    function countRun(text, index, char) {
        let end = index;
        while (end < text.length && text[end] === char) end += 1;
        return end - index;
    }

    function findMatchingCodeFence(text, start, runLength) {
        let index = start;
        while (index < text.length) {
            if (text[index] === '`') {
                const length = countRun(text, index, '`');
                if (length === runLength) return index;
                index += length;
                continue;
            }
            index += 1;
        }
        return -1;
    }

    function parseCodeSpan(text, index) {
        const runLength = countRun(text, index, '`');
        const contentStart = index + runLength;
        const close = findMatchingCodeFence(text, contentStart, runLength);
        if (close < 0) return null;

        let content = text.slice(contentStart, close).replace(/\r?\n/g, ' ');
        if (/^ .* $/.test(content) && !/^ +$/.test(content)) {
            content = content.slice(1, -1);
        }

        return {
            html: `<code>${escapeHtml(content)}</code>`,
            next: close + runLength
        };
    }

    function findClosingBracket(text, openIndex) {
        let depth = 0;
        for (let index = openIndex; index < text.length; index += 1) {
            const char = text[index];
            if (char === '\\') {
                index += 1;
                continue;
            }
            if (char === '`') {
                const code = parseCodeSpan(text, index);
                if (code) {
                    index = code.next - 1;
                    continue;
                }
            }
            if (char === '[') depth += 1;
            else if (char === ']') {
                depth -= 1;
                if (depth === 0) return index;
            }
        }
        return -1;
    }

    function parseDestinationAndTitle(rawValue) {
        const value = String(rawValue ?? '').trim();
        if (!value) return null;

        let destination = '';
        let rest = '';

        if (value.startsWith('<')) {
            const close = value.indexOf('>');
            if (close < 1) return null;
            destination = value.slice(1, close);
            rest = value.slice(close + 1).trim();
        } else {
            let splitAt = -1;
            for (let index = 0; index < value.length; index += 1) {
                if (/\s/.test(value[index])) {
                    splitAt = index;
                    break;
                }
            }
            destination = splitAt < 0 ? value : value.slice(0, splitAt);
            rest = splitAt < 0 ? '' : value.slice(splitAt).trim();
        }

        let title = null;
        if (rest) {
            const first = rest[0];
            const last = rest[rest.length - 1];
            const quoted = (first === '"' && last === '"') ||
                (first === "'" && last === "'") ||
                (first === '(' && last === ')');
            if (!quoted || rest.length < 2) return null;
            title = rest.slice(1, -1);
        }

        return { destination, title };
    }

    function parseLinkDestination(text, openParenIndex) {
        if (text[openParenIndex] !== '(') return null;
        let depth = 0;
        let value = '';

        for (let index = openParenIndex; index < text.length; index += 1) {
            const char = text[index];
            if (char === '\\' && index + 1 < text.length) {
                if (index > openParenIndex) value += text[index + 1];
                index += 1;
                continue;
            }
            if (char === '(') {
                depth += 1;
                if (depth > 1) value += char;
                continue;
            }
            if (char === ')') {
                depth -= 1;
                if (depth === 0) {
                    const parsed = parseDestinationAndTitle(value);
                    return parsed ? { ...parsed, next: index + 1 } : null;
                }
                if (depth < 0) return null;
                value += char;
                continue;
            }
            if (depth > 0) value += char;
        }

        return null;
    }

    function normalizeReferenceLabel(value) {
        return String(value ?? '').trim().replace(/\s+/g, ' ').toLowerCase();
    }

    function parseReferenceDefinition(line) {
        const match = String(line ?? '').match(/^\s{0,3}\[([^\]]+)\]:\s*(.+?)\s*$/);
        if (!match) return null;
        const parsed = parseDestinationAndTitle(match[2]);
        if (!parsed) return null;
        const safe = safeUrl(parsed.destination);
        if (safe === '#') return null;
        return {
            label: normalizeReferenceLabel(match[1]),
            destination: safe,
            title: parsed.title
        };
    }

    function extractReferenceDefinitions(lines, inheritedReferences = null) {
        const references = new Map(inheritedReferences ? [...inheritedReferences.entries()] : []);
        const contentLines = [];
        for (const line of lines) {
            const definition = parseReferenceDefinition(line);
            if (definition) {
                references.set(definition.label, definition);
                continue;
            }
            contentLines.push(line);
        }
        return { lines: contentLines, references };
    }

    function stripTrailingUrlPunctuation(url) {
        let value = url;
        while (/[.,!?;:]$/.test(value)) value = value.slice(0, -1);

        // Keep balanced closing parentheses in ordinary URLs while avoiding the
        // common prose case: "https://example.com/foo)."
        while (value.endsWith(')')) {
            const opens = (value.match(/\(/g) || []).length;
            const closes = (value.match(/\)/g) || []).length;
            if (closes <= opens) break;
            value = value.slice(0, -1);
        }
        return value;
    }

    function tokenizeProtectedInline(text, references = null) {
        const tokens = [];
        let plain = '';

        const placeholder = (html) => {
            const id = tokens.length;
            tokens.push(html);
            return `\u0000SOR${id}\u0000`;
        };

        for (let index = 0; index < text.length;) {
            const char = text[index];

            if (char === '\\' && index + 1 < text.length && ESCAPABLE.test(text[index + 1])) {
                plain += placeholder(escapeHtml(text[index + 1]));
                index += 2;
                continue;
            }

            if (char === '&') {
                const entity = text.slice(index).match(/^&(?:#\d+|#x[0-9A-Fa-f]+|amp|lt|gt|quot|apos|nbsp);/);
                if (entity) {
                    plain += placeholder(entity[0]);
                    index += entity[0].length;
                    continue;
                }
            }

            if (char === '`') {
                const code = parseCodeSpan(text, index);
                if (code) {
                    plain += placeholder(code.html);
                    index = code.next;
                    continue;
                }
            }

            const image = char === '!' && text[index + 1] === '[';
            const link = char === '[';
            if (image || link) {
                const openBracket = image ? index + 1 : index;
                const closeBracket = findClosingBracket(text, openBracket);
                if (closeBracket >= 0) {
                    const label = text.slice(openBracket + 1, closeBracket);
                    const labelHtml = inlineMarkdown(label, references);
                    let resolved = null;
                    let next = closeBracket + 1;

                    if (text[next] === '(') {
                        const destination = parseLinkDestination(text, next);
                        if (destination) {
                            const safe = safeUrl(destination.destination);
                            if (safe !== '#') {
                                resolved = { destination: safe, title: destination.title };
                                next = destination.next;
                            }
                        }
                    } else if (references) {
                        let referenceLabel = null;
                        if (text[next] === '[') {
                            const refClose = text.indexOf(']', next + 1);
                            if (refClose >= 0) {
                                referenceLabel = text.slice(next + 1, refClose) || label;
                                next = refClose + 1;
                            }
                        } else {
                            referenceLabel = label;
                        }
                        if (referenceLabel != null) {
                            const reference = references.get(normalizeReferenceLabel(referenceLabel));
                            if (reference) resolved = reference;
                        }
                    }

                    if (resolved) {
                        const titleAttr = resolved.title == null
                            ? ''
                            : ` title="${escapeHtml(resolved.title)}"`;
                        // Remote image loading is intentionally suppressed. Image
                        // syntax is rendered as a safe clickable alt-label instead.
                        const html = `<a href="${escapeHtml(resolved.destination)}" target="_blank" rel="noopener noreferrer"${titleAttr}>${labelHtml}</a>`;
                        plain += placeholder(html);
                        index = next;
                        continue;
                    }
                }
            }

            if (char === '<') {
                const br = text.slice(index).match(/^<br\s*\/?\s*>/i);
                if (br) {
                    plain += placeholder('<br>');
                    index += br[0].length;
                    continue;
                }

                const close = text.indexOf('>', index + 1);
                if (close > index + 1) {
                    const inside = text.slice(index + 1, close);
                    const safe = safeUrl(inside);
                    if (safe !== '#') {
                        plain += placeholder(
                            `<a href="${escapeHtml(safe)}" target="_blank" rel="noopener noreferrer">${escapeHtml(inside)}</a>`
                        );
                        index = close + 1;
                        continue;
                    }
                }
            }

            if (/^https?:\/\//i.test(text.slice(index))) {
                const match = text.slice(index).match(/^https?:\/\/[^\s<]+/i);
                if (match) {
                    const raw = match[0];
                    const url = stripTrailingUrlPunctuation(raw);
                    if (url) {
                        plain += placeholder(
                            `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(url)}</a>`
                        );
                        plain += raw.slice(url.length);
                        index += raw.length;
                        continue;
                    }
                }
            }

            plain += char;
            index += 1;
        }

        return { plain, tokens };
    }

    function restoreInlineTokens(html, tokens) {
        return html.replace(/\u0000SOR(\d+)\u0000/g, (_match, index) => tokens[Number(index)] ?? '');
    }

    function inlineMarkdown(text, references = null) {
        const { plain, tokens } = tokenizeProtectedInline(String(text ?? ''), references);
        let html = escapeHtml(plain);

        // These operate only on the escaped, protected remainder. Code spans,
        // links and autolinks have already been removed from delimiter parsing.
        html = html.replace(/\*\*\*([^*\n]+?)\*\*\*/g, '<strong><em>$1</em></strong>');
        html = html.replace(/\*\*([^*\n]+?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/__([^_\n]+?)__/g, '<strong>$1</strong>');
        html = html.replace(/~~([^~\n]+?)~~/g, '<del>$1</del>');
        html = html.replace(/(^|[^*])\*([^*\n]+?)\*/g, '$1<em>$2</em>');
        html = html.replace(/(^|[^_\w])_([^_\n]+?)_/g, '$1<em>$2</em>');

        return restoreInlineTokens(html, tokens);
    }

    function trimOuterTablePipes(line) {
        let value = line.trim();
        if (value.startsWith('|')) value = value.slice(1);
        if (value.endsWith('|')) {
            let slashCount = 0;
            for (let index = value.length - 2; index >= 0 && value[index] === '\\'; index -= 1) slashCount += 1;
            if (slashCount % 2 === 0) value = value.slice(0, -1);
        }
        return value;
    }

    function splitTableRow(line) {
        const value = trimOuterTablePipes(line);
        const cells = [];
        let cell = '';
        let codeFenceLength = 0;
        let bracketDepth = 0;
        let parenDepth = 0;

        for (let index = 0; index < value.length; index += 1) {
            const char = value[index];

            if (char === '\\' && index + 1 < value.length) {
                cell += char + value[index + 1];
                index += 1;
                continue;
            }

            if (char === '`') {
                const runLength = countRun(value, index, '`');
                if (!codeFenceLength) codeFenceLength = runLength;
                else if (runLength === codeFenceLength) codeFenceLength = 0;
                cell += value.slice(index, index + runLength);
                index += runLength - 1;
                continue;
            }

            if (!codeFenceLength) {
                if (char === '[') bracketDepth += 1;
                else if (char === ']' && bracketDepth > 0) bracketDepth -= 1;
                else if (char === '(' && bracketDepth === 0) parenDepth += 1;
                else if (char === ')' && bracketDepth === 0 && parenDepth > 0) parenDepth -= 1;

                if (char === '|' && bracketDepth === 0 && parenDepth === 0) {
                    cells.push(cell.trim());
                    cell = '';
                    continue;
                }
            }

            cell += char;
        }

        cells.push(cell.trim());
        return cells;
    }

    function tableAlignment(cell) {
        const value = cell.trim();
        if (!/^:?-{3,}:?$/.test(value)) return null;
        if (value.startsWith(':') && value.endsWith(':')) return 'center';
        if (value.endsWith(':')) return 'right';
        return 'left';
    }

    function parseTableSeparator(line) {
        if (!line.includes('|')) return null;
        const cells = splitTableRow(line);
        if (cells.length < 2) return null;
        const alignments = cells.map(tableAlignment);
        return alignments.every(Boolean) ? alignments : null;
    }

    function indentationWidth(value) {
        let width = 0;
        for (const char of String(value ?? '')) width += char === '\t' ? 4 : 1;
        return width;
    }

    function matchListItem(line) {
        const match = String(line ?? '').match(/^(\s*)([-*+]|\d+[.)])\s+(.+)$/);
        if (!match) return null;
        return {
            indent: indentationWidth(match[1]),
            ordered: /^\d/.test(match[2]),
            content: match[3]
        };
    }

    function leadingIndentWidth(line) {
        const match = String(line ?? '').match(/^(\s*)/);
        return indentationWidth(match ? match[1] : '');
    }

    function renderListItemLead(content, references = null) {
        const task = String(content ?? '').match(/^\[([ xX])\]\s+(.*)$/);
        if (!task) return inlineMarkdown(content, references);
        const checked = task[1].toLowerCase() === 'x';
        return `<input type="checkbox" disabled${checked ? ' checked' : ''}> ${inlineMarkdown(task[2], references)}`;
    }

    function renderList(lines, startIndex, references = null) {
        const first = matchListItem(lines[startIndex]);
        if (!first) return null;

        const baseIndent = first.indent;
        const ordered = first.ordered;
        const tag = ordered ? 'ol' : 'ul';
        const items = [];
        let index = startIndex;

        while (index < lines.length) {
            const item = matchListItem(lines[index]);
            if (!item || item.indent !== baseIndent || item.ordered !== ordered) break;

            const childLines = [];
            index += 1;

            while (index < lines.length) {
                const next = lines[index];
                const nextItem = matchListItem(next);
                if (nextItem && nextItem.indent === baseIndent) break;
                if (nextItem && nextItem.indent < baseIndent) break;
                if (next.trim() && leadingIndentWidth(next) <= baseIndent && !nextItem) break;

                if (!next.trim()) {
                    // Preserve a blank only when it separates indented child content.
                    const following = index + 1 < lines.length ? lines[index + 1] : '';
                    if (following && leadingIndentWidth(following) > baseIndent) childLines.push('');
                    index += 1;
                    continue;
                }

                childLines.push(next);
                index += 1;
            }

            let html = renderListItemLead(item.content, references);
            if (childLines.length) {
                const nonBlank = childLines.filter((line) => line.trim());
                const childIndent = nonBlank.length
                    ? Math.min(...nonBlank.map(leadingIndentWidth))
                    : baseIndent + 2;
                const normalizedChildren = childLines.map((line) => {
                    if (!line.trim()) return '';
                    let remaining = childIndent;
                    let cursor = 0;
                    while (cursor < line.length && remaining > 0) {
                        if (line[cursor] === '\t') remaining -= 4;
                        else if (line[cursor] === ' ') remaining -= 1;
                        else break;
                        cursor += 1;
                    }
                    return line.slice(cursor);
                });
                html += renderMarkdown(normalizedChildren.join('\n'), references);
            }
            items.push(`<li>${html}</li>`);
        }

        return { html: `<${tag}>${items.join('')}</${tag}>`, next: index };
    }

    function lineStartsBlock(lines, index) {
        const line = lines[index] || '';
        if (!line.trim()) return true;
        if (/^\s*(`{3,}|~{3,})/.test(line)) return true;
        if (/^\s*#{1,6}\s+/.test(line)) return true;
        if (/^\s*>/.test(line)) return true;
        if (/^\s*[-*+]\s+/.test(line)) return true;
        if (/^\s*\d+[.)]\s+/.test(line)) return true;
        if (/^\s*(?:-{3,}|\*\s*\*\s*\*|_{3,})\s*$/.test(line)) return true;
        if (index + 1 < lines.length && parseTableSeparator(lines[index + 1])) return true;
        return false;
    }

    function renderMarkdown(markdown, inheritedReferences = null) {
        const rawLines = String(markdown ?? '').replace(/\r\n?/g, '\n').split('\n');
        const extracted = extractReferenceDefinitions(rawLines, inheritedReferences);
        const lines = extracted.lines;
        const references = extracted.references;
        const out = [];
        let index = 0;

        while (index < lines.length) {
            const line = lines[index];

            if (!line.trim()) {
                index += 1;
                continue;
            }

            const fence = line.match(/^\s*(`{3,}|~{3,})(.*)$/);
            if (fence) {
                const markerChar = fence[1][0];
                const markerLength = fence[1].length;
                const language = fence[2].trim();
                const code = [];
                index += 1;
                const closePattern = new RegExp(`^\\s*${markerChar}{${markerLength},}\\s*$`);

                while (index < lines.length && !closePattern.test(lines[index])) {
                    code.push(lines[index]);
                    index += 1;
                }
                if (index < lines.length) index += 1;

                const className = language
                    ? ` class="language-${escapeHtml(language.replace(/[^A-Za-z0-9_+.-]/g, ''))}"`
                    : '';
                out.push(`<pre><code${className}>${escapeHtml(code.join('\n'))}</code></pre>`);
                continue;
            }

            const heading = line.match(/^\s*(#{1,6})\s+(.+?)\s*#*\s*$/);
            if (heading) {
                const level = heading[1].length;
                out.push(`<h${level}>${inlineMarkdown(heading[2], references)}</h${level}>`);
                index += 1;
                continue;
            }

            if (/^\s*(?:-{3,}|\*\s*\*\s*\*|_{3,})\s*$/.test(line)) {
                out.push('<hr>');
                index += 1;
                continue;
            }

            if (/^\s*>/.test(line)) {
                const quote = [];
                while (index < lines.length && /^\s*>/.test(lines[index])) {
                    quote.push(lines[index].replace(/^\s*>\s?/, ''));
                    index += 1;
                }
                out.push(`<blockquote>${renderMarkdown(quote.join('\n'), references)}</blockquote>`);
                continue;
            }

            const alignments = index + 1 < lines.length
                ? parseTableSeparator(lines[index + 1])
                : null;
            if (alignments) {
                const headers = splitTableRow(line);
                const columnCount = Math.max(headers.length, alignments.length);
                index += 2;
                const rows = [];

                while (index < lines.length && lines[index].trim()) {
                    const cells = splitTableRow(lines[index]);
                    if (cells.length < 2 || !lines[index].includes('|')) break;
                    rows.push(cells);
                    index += 1;
                }

                out.push('<table><thead><tr>');
                for (let cellIndex = 0; cellIndex < columnCount; cellIndex += 1) {
                    const align = alignments[cellIndex] || 'left';
                    out.push(`<th style="text-align:${align}">${inlineMarkdown(headers[cellIndex] || '', references)}</th>`);
                }
                out.push('</tr></thead>');

                if (rows.length) {
                    out.push('<tbody>');
                    rows.forEach((row) => {
                        out.push('<tr>');
                        for (let cellIndex = 0; cellIndex < columnCount; cellIndex += 1) {
                            const align = alignments[cellIndex] || 'left';
                            out.push(`<td style="text-align:${align}">${inlineMarkdown(row[cellIndex] || '', references)}</td>`);
                        }
                        out.push('</tr>');
                    });
                    out.push('</tbody>');
                }
                out.push('</table>');
                continue;
            }

            const renderedList = matchListItem(line) ? renderList(lines, index, references) : null;
            if (renderedList) {
                out.push(renderedList.html);
                index = renderedList.next;
                continue;
            }

            const paragraph = [line];
            index += 1;
            while (index < lines.length && !lineStartsBlock(lines, index)) {
                paragraph.push(lines[index]);
                index += 1;
            }
            out.push(`<p>${inlineMarkdown(paragraph.join('\n'), references).replace(/\n/g, '<br>')}</p>`);
        }

        return out.join('');
    }

    window.aiDirectorRenderMarkdown = renderMarkdown;
})();
