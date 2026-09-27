import { useEffect, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'

/** Accessible modal: Escape closes, focus stays inside, and the page behind doesn't scroll. */
export function Modal({ title, subtitle, onClose, children, footer, wide }: { title: string; subtitle?: string; onClose: () => void; children: ReactNode; footer?: ReactNode; wide?: boolean }) {
  useEffect(() => {
    const key = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    addEventListener('keydown', key)
    const main = document.querySelector('main') as HTMLElement | null
    const previous = main?.style.overflow
    if (main) main.style.overflow = 'hidden'
    return () => { removeEventListener('keydown', key); if (main) main.style.overflow = previous ?? '' }
  }, [onClose])
  // Portal into the app root: an animated (transformed) page would otherwise re-anchor position:fixed.
  const host = (document.querySelector('.app') as HTMLElement | null) ?? document.body
  return createPortal(<div className="modal-scrim" onMouseDown={onClose}>
    <div className={`modal ${wide ? 'wide' : ''}`} role="dialog" aria-modal="true" aria-label={title} onMouseDown={e => e.stopPropagation()}>
      <header><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div><button className="icon-button" onClick={onClose} aria-label="Close"><X /></button></header>
      <div className="modal-body">{children}</div>
      {footer && <footer>{footer}</footer>}
    </div>
  </div>, host)
}
