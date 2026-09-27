import { useMemo, useState } from 'react'

export type Row = { kind: 'same' | 'add' | 'del'; text: string }

/** Line-level diff (LCS). Reordered skill lists read as one clear before/after pair instead of scattered words. */
export function diffLines(before: string, after: string): Row[] {
  const a = before.split('\n'), b = after.split('\n')
  if (a.length * b.length > 2_000_000) return [...a.map(text => ({ kind: 'del' as const, text })), ...b.map(text => ({ kind: 'add' as const, text }))]
  const table = Array.from({ length: a.length + 1 }, () => new Uint32Array(b.length + 1))
  for (let i = a.length - 1; i >= 0; i--) for (let j = b.length - 1; j >= 0; j--) table[i][j] = a[i] === b[j] ? table[i + 1][j + 1] + 1 : Math.max(table[i + 1][j], table[i][j + 1])
  const rows: Row[] = []
  let i = 0, j = 0
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) { rows.push({ kind: 'same', text: a[i] }); i++; j++ }
    else if (table[i + 1][j] >= table[i][j + 1]) rows.push({ kind: 'del', text: a[i++] })
    else rows.push({ kind: 'add', text: b[j++] })
  }
  while (i < a.length) rows.push({ kind: 'del', text: a[i++] })
  while (j < b.length) rows.push({ kind: 'add', text: b[j++] })
  return rows
}

/** Highlight list items whose position changed between an old and a new line. */
function movedItems(oldLine: string, newLine: string) {
  const items = (line: string) => line.slice(line.indexOf(':') + 1).split(',').map(x => x.trim()).filter(Boolean)
  const before = items(oldLine), after = items(newLine)
  return new Set(after.filter((item, index) => before.indexOf(item) !== index))
}

function AddedLine({ text, previous }: { text: string; previous?: string }) {
  if (!previous || !text.includes(',')) return <>{text}</>
  const moved = movedItems(previous, text)
  const colon = text.indexOf(':')
  const label = colon >= 0 ? text.slice(0, colon + 1) + ' ' : ''
  const list = (colon >= 0 ? text.slice(colon + 1) : text).split(',').map(x => x.trim()).filter(Boolean)
  return <>{label}{list.map((item, i) => <span key={i}>{moved.has(item) ? <b className="moved">{item}</b> : item}{i < list.length - 1 ? ', ' : ''}</span>)}</>
}

export function WordDiff({ before, after }: { before: string; after: string }) {
  const rows = useMemo(() => diffLines(before, after), [before, after])
  const [expanded, setExpanded] = useState(false)
  const changed = rows.filter(r => r.kind === 'add').length
  // Collapse long runs of unchanged lines, keeping two lines of context around each change.
  const near = new Set<number>()
  rows.forEach((r, i) => { if (r.kind !== 'same') for (let k = i - 2; k <= i + 2; k++) near.add(k) })
  const blocks: ({ gap: number } | { row: Row; index: number })[] = []
  rows.forEach((row, index) => {
    if (expanded || near.has(index) || !changed) return blocks.push({ row, index })
    const last = blocks[blocks.length - 1]
    if (last && 'gap' in last) last.gap += 1
    else blocks.push({ gap: 1 })
  })
  return <div className="word-diff">
    <div className="diff-legend"><span className="add">{changed ? `${changed} line${changed === 1 ? '' : 's'} changed` : 'No changes needed — your CV already leads with this job’s skills'}</span>{changed > 0 && <span className="moved-legend">Bold = moved forward for this job</span>}
      {rows.length > 12 && <button className="link" onClick={() => setExpanded(!expanded)}>{expanded ? 'Show changes only' : 'Show full CV'}</button>}</div>
    <div className="diff-lines">{blocks.map((block, i) => 'gap' in block
      ? <button key={i} className="diff-gap" onClick={() => setExpanded(true)}>··· {block.gap} unchanged line{block.gap === 1 ? '' : 's'} ···</button>
      : <div key={i} className={`diff-line ${block.row.kind}`}><span className="gutter">{block.row.kind === 'add' ? '+' : block.row.kind === 'del' ? '−' : ''}</span>
        <span>{block.row.kind === 'add' ? <AddedLine text={block.row.text} previous={rows[block.index - 1]?.kind === 'del' ? rows[block.index - 1].text : undefined} /> : block.row.text || ' '}</span></div>)}</div>
  </div>
}
