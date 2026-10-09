const tabNames = {
  overview: ['Platform overview', 'Architecture boundaries and trust zones'],
  responsibilities: ['Component responsibilities', 'Logical service boundaries and authority'],
  request: ['One request · N work items', 'One durable workflow owns the dependency graph'],
  natural: ['Natural-language request', 'Conversation Manager → Orchestrator → policy → one workflow'],
  prepare: ['Preparation and consent', 'Agent preparation ends before the customer is asked'],
  resume: ['Consent and workflow resume', 'Structured consent bypasses the Orchestrator'],
  statuses: ['Request and response statuses', 'Acknowledgement is not a bank outcome'],
  ownership: ['Caller · executor · state owner', 'Authority follows responsibility'],
  contracts: ['API contracts', 'Stable typed APIs and service identities'],
  technology: ['Technology mapping', 'Prototype choices preserve production boundaries'],
}

let initialMermaidRender = Promise.resolve()
if (window.mermaid) {
  window.mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', theme: 'neutral' })
  initialMermaidRender = window.mermaid.run({ querySelector: '.mermaid' })
}

const escapeHtml = (value) => value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;')
const inlineMarkdown = (value) => escapeHtml(value).replace(/`([^`]+)`/g, '<code>$1</code>').replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')

function renderMarkdown(markdown) {
  const lines = markdown.split(/\r?\n/)
  const output = []
  let index = 0
  while (index < lines.length) {
    const line = lines[index]
    if (!line.trim() || /^---+$/.test(line.trim())) { index += 1; continue }
    const fence = line.match(/^```([\w-]*)/)
    if (fence) {
      const language = fence[1]
      const code = []
      index += 1
      while (index < lines.length && !/^```/.test(lines[index])) code.push(lines[index++])
      index += 1
      if (language === 'mermaid') output.push(`<pre class="mermaid">${escapeHtml(code.join('\n'))}</pre>`)
      else output.push(`<pre class="markdown-code"><code>${escapeHtml(code.join('\n'))}</code></pre>`)
      continue
    }
    if (/^\|/.test(line) && /^\|?[\s:|-]+\|?$/.test(lines[index + 1] ?? '')) {
      const cells = (entry) => entry.replace(/^\||\|$/g, '').split('|').map((cell) => cell.trim())
      const headings = cells(line)
      index += 2
      const rows = []
      while (index < lines.length && /^\|/.test(lines[index])) rows.push(cells(lines[index++]))
      output.push(`<div class="markdown-table"><table><thead><tr>${headings.map((cell) => `<th>${inlineMarkdown(cell)}</th>`).join('')}</tr></thead><tbody>${rows.map((row) => `<tr>${row.map((cell) => `<td>${inlineMarkdown(cell)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`)
      continue
    }
    const heading = line.match(/^(#{1,4})\s+(.*)/)
    if (heading) {
      const level = Math.min(4, heading[1].length + 1)
      output.push(`<h${level}>${inlineMarkdown(heading[2])}</h${level}>`)
      index += 1
      continue
    }
    if (/^>\s?/.test(line)) {
      const quote = []
      while (index < lines.length && /^>\s?/.test(lines[index])) quote.push(lines[index++].replace(/^>\s?/, ''))
      output.push(`<aside class="markdown-callout">${quote.map((entry) => `<p>${inlineMarkdown(entry)}</p>`).join('')}</aside>`)
      continue
    }
    if (/^\s*[-*]\s+/.test(line)) {
      const items = []
      while (index < lines.length && /^\s*[-*]\s+/.test(lines[index])) items.push(`<li>${inlineMarkdown(lines[index++].replace(/^\s*[-*]\s+/, ''))}</li>`)
      output.push(`<ul>${items.join('')}</ul>`)
      continue
    }
    const paragraph = [line]
    index += 1
    while (index < lines.length && lines[index].trim() && !/^(#{1,4}\s|```|>\s?|\|)/.test(lines[index]) && !/^\s*[-*]\s+/.test(lines[index])) paragraph.push(lines[index++])
    output.push(`<p>${inlineMarkdown(paragraph.join(' '))}</p>`)
  }
  return output.join('')
}

initialMermaidRender
  .catch(() => undefined)
  .then(() => fetch('content/architecture-summary.md'))
  .then((response) => {
    if (!response.ok) throw new Error('Architecture source unavailable')
    return response.text()
  })
  .then((markdown) => {
    document.querySelector('#markdown-source').innerHTML = renderMarkdown(markdown)
    if (window.mermaid) void window.mermaid.run({ querySelector: '#markdown-source .mermaid' }).catch(() => undefined)
  })
  .catch(() => {
    document.querySelector('.source-content').hidden = true
  })

const tabs = [...document.querySelectorAll('.tabs button')]
const panels = [...document.querySelectorAll('.tab-panel')]
const title = document.querySelector('#section-title')
const subtitle = document.querySelector('#section-subtitle')
const toolbar = document.querySelector('.toolbar')
let previousScroll = 0

tabs.forEach((button) => button.addEventListener('click', () => {
  const id = button.dataset.tab
  tabs.forEach((entry) => entry.classList.toggle('active', entry === button))
  panels.forEach((panel) => panel.classList.toggle('active', panel.id === `tab-${id}`))
  title.textContent = tabNames[id][0]
  subtitle.textContent = tabNames[id][1]
  window.scrollTo({ top: 0, behavior: 'smooth' })
}))

document.querySelector('#theme-toggle').addEventListener('click', () => document.body.classList.toggle('dark'))
document.querySelector('#collapse-header').addEventListener('click', (event) => {
  const collapsed = document.querySelector('.site-header').classList.toggle('collapsed')
  event.currentTarget.textContent = collapsed ? 'Show header' : 'Collapse header'
  toolbar.style.top = collapsed ? '0' : '68px'
})

const zoomSelect = document.querySelector('#zoom-select')
zoomSelect.addEventListener('change', () => {
  document.querySelectorAll('.tab-panel.active .diagram-board,.tab-panel.active .sequence-diagram,.tab-panel.active .mermaid-shell .mermaid').forEach((diagram) => {
    const scale = zoomSelect.value === 'fit'
      ? Math.min(1, diagram.parentElement.clientWidth / diagram.scrollWidth)
      : Number(zoomSelect.value)
    diagram.style.transform = `scale(${scale})`
    diagram.style.marginBottom = `${Math.max(0, (scale - 1) * diagram.offsetHeight)}px`
  })
})

document.querySelector('#reset-view').addEventListener('click', () => {
  document.querySelectorAll('.diagram-board,.sequence-diagram,.mermaid-shell .mermaid').forEach((diagram) => {
    diagram.style.transform = ''
    diagram.style.marginBottom = ''
  })
  document.querySelectorAll('.diagram-shell.maximized').forEach((diagram) => diagram.classList.remove('maximized'))
  document.querySelectorAll('.diagram-scroll').forEach((container) => {
    container.scrollTo({ top: 0, left: 0, behavior: 'smooth' })
  })
  zoomSelect.value = '1'
  window.scrollTo({ top: 0, behavior: 'smooth' })
})

document.querySelector('#maximize').addEventListener('click', () => {
  const activeDiagram = document.querySelector('.tab-panel.active .diagram-shell')
  if (!activeDiagram) return
  const wasMaximized = activeDiagram.classList.contains('maximized')
  document.querySelectorAll('.diagram-shell.maximized').forEach((diagram) => diagram.classList.remove('maximized'))
  if (!wasMaximized) {
    previousScroll = window.scrollY
    activeDiagram.classList.add('maximized')
    activeDiagram.querySelector('.diagram-scroll').focus()
  } else {
    window.scrollTo({ top: previousScroll })
  }
})

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') {
    document.querySelectorAll('.diagram-shell.maximized').forEach((diagram) => diagram.classList.remove('maximized'))
    window.scrollTo({ top: previousScroll })
  }
})
