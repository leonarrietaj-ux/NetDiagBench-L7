"""
Helper global para Tooltips y Cuadros de Descripción de NetDiagBench-L7.
Unifica 100% el estilo visual con la barra superior de acciones (Imagen 1 / .header-action-tooltip):
- Diseño compacto, plano y esbelto (padding: 4px 8px, border-radius: 6px).
- Fondo #0f172a (dark slate) y borde 1px solid rgba(148, 163, 184, 0.35) con texto #f8fafc.
- Modo Día: fondo blanco #ffffff con borde #cbd5e1 y texto institucional #003366.
- Sin flechas ni cabeceras con íconos para máxima consistencia visual.
- Soporte e intercepción universal para:
  1. Íconos informativos y tarjetas KPI (ℹ️).
  2. Elementos gráficos SVG (<circle>, <rect>, etc. con <title>) suprimiendo el tooltip nativo del SO.
  3. Elementos con atributos title, data-tooltip o data-custom-tooltip.
"""

TOOLTIP_CSS = """
/* ================= TOOLTIPS GLOBALES UNIFICADOS (ESTILO IMAGEN 1: SLATE COMPACTO) ================= */
.netdiag-custom-tooltip {
    position: fixed;
    z-index: 99999999;
    max-width: 340px;
    padding: 4px 8px;
    border-radius: 6px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 0.72rem;
    font-weight: 600;
    line-height: 1.35;
    pointer-events: none;
    user-select: none;
    opacity: 0;
    transform: translateY(3px) scale(0.98);
    transition: opacity 0.15s ease-in-out, transform 0.15s ease-in-out;
    display: none;
    white-space: normal;

    /* Modo Oscuro Unificado (Idéntico a Imagen 1: .header-action-tooltip) */
    background: #0f172a;
    color: #f8fafc;
    border: 1px solid rgba(148, 163, 184, 0.35);
    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.4);
}

.netdiag-custom-tooltip.tooltip-visible {
    opacity: 1;
    transform: translateY(0) scale(1);
}

.netdiag-custom-tooltip .tooltip-header {
    display: none !important;
}

.netdiag-custom-tooltip .tooltip-body {
    color: #f8fafc;
    font-size: 0.72rem;
    font-weight: 600;
    line-height: 1.35;
    word-break: break-word;
}

.netdiag-custom-tooltip .tooltip-kbd {
    display: inline-block;
    padding: 1px 4px;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 0.68rem;
    font-weight: 700;
    background: rgba(255, 255, 255, 0.12);
    color: #ffffff;
    border: 1px solid rgba(255, 255, 255, 0.25);
    border-radius: 3px;
    margin: 0 2px;
}

/* Se elimina cualquier flecha para mantener el diseño plano, rectangular y estilizado de la Imagen 1 */
.netdiag-custom-tooltip .tooltip-arrow {
    display: none !important;
}

/* Modo Día / Claro Unificado */
[data-theme="light"] .netdiag-custom-tooltip,
.light-theme .netdiag-custom-tooltip,
html[data-theme="light"] .netdiag-custom-tooltip,
body.light-theme .netdiag-custom-tooltip {
    background: #ffffff !important;
    color: #003366 !important;
    border: 1px solid #cbd5e1 !important;
    box-shadow: 0 4px 16px rgba(0, 51, 102, 0.15) !important;
}

[data-theme="light"] .netdiag-custom-tooltip .tooltip-body,
.light-theme .netdiag-custom-tooltip .tooltip-body,
html[data-theme="light"] .netdiag-custom-tooltip .tooltip-body,
body.light-theme .netdiag-custom-tooltip .tooltip-body {
    color: #003366 !important;
    font-weight: 600 !important;
}

[data-theme="light"] .netdiag-custom-tooltip .tooltip-kbd,
.light-theme .netdiag-custom-tooltip .tooltip-kbd,
html[data-theme="light"] .netdiag-custom-tooltip .tooltip-kbd,
body.light-theme .netdiag-custom-tooltip .tooltip-kbd {
    background: #f1f5f9 !important;
    color: #003366 !important;
    border: 1px solid #cbd5e1 !important;
}

/* Micro-efecto visual para elementos con ayuda */
span[style*="cursor:help"], span[style*="cursor: help"], .cursor-help {
    cursor: help;
}
"""

TOOLTIP_JS = """
<script>
(function() {
    let tooltipEl = null;
    let currentTarget = null;
    let hideTimer = null;
    let showTimer = null;

    // Selector Global: Captura elementos candidatos a contener descripciones técnicas
    const CANDIDATE_SELECTOR = '[title], [data-tooltip], [data-custom-tooltip], [data-help], .cursor-help, [style*="cursor:help"], [style*="cursor: help"], [data-tooltip-info], [data-metric-info], svg circle, svg rect, svg path, svg polygon';

    // Reglas estrictas de diseño UX/UI (Entorno Táctico Premium NOC):
    // Preserva los tooltips unificados en íconos técnicos informativos (ℹ️), métricas complejas y puntos gráficos SVG.
    function isEligibleForTooltip(el) {
        if (!el || el === document.body || el === document.documentElement) return false;

        // 1. Prohibido: Marcos y contenedores iframe
        if (el.tagName && el.tagName.toLowerCase() === 'iframe') return false;
        if (el.id === 'mainViewIframe' || (el.closest && el.closest('iframe, #mainViewIframe'))) return false;

        // 2. Prohibido: Botones con sus propios tooltips estáticos CSS (.header-action-tooltip / .toolbar-action-tooltip)
        if (el.closest && el.closest('.toolbar-btn-group, .header-action-tooltip, .toolbar-action-tooltip')) return false;

        // 3. Prohibido: Menú lateral (Sidebar) y pestañas de navegación con texto
        if (el.closest && el.closest('.btn-panel-action, #sidebarNavAccordion, .nav-tab, [data-no-tooltip]')) return false;

        // 4. Prohibido: Controles Universales con texto auto-descriptivo
        if (el.closest && el.closest('#btnCommandPalette, #themeToggleBtnHeader, #themeToggleBtn, .cmd-palette-trigger-btn, .theme-toggle-corner, #sidebarResizer')) return false;

        // 5. Prohibido: Paneles de lectura estáticos de texto
        if (el.closest && el.closest('#groundTruthInfo, .problem-statement-card, .verdict-subbox, #findings')) return false;

        // 6. Prohibido: Botones o enlaces con texto explícito auto-descriptivo sin ícono de ayuda
        const btnOrLink = el.closest && el.closest('button, a');
        if (btnOrLink && !el.closest('.cursor-help, .info-icon, [data-tooltip-info], [data-metric-info]')) {
            const btnText = btnOrLink.textContent ? btnOrLink.textContent.trim() : '';
            if (btnText.length > 2 && !btnText.includes('ℹ️')) {
                return false;
            }
        }

        // 7. Permitido: Puntos de datos y figuras SVG en gráficos analíticos (Bootstrap, Radar, Correlación)
        if (el.tagName && ['circle', 'rect', 'path', 'polygon', 'g'].includes(el.tagName.toLowerCase())) {
            const hasTitle = (el.querySelector && el.querySelector('title')) || (el.parentElement && el.parentElement.querySelector && el.parentElement.querySelector('title'));
            if (hasTitle || el.dataset?.customTooltip || el.getAttribute('title')) {
                return true;
            }
        }

        // 8. Permitido: Íconos de Información Técnica (ℹ️) y métricas con cursor:help
        const text = el.textContent || '';
        const isInfoIcon = text.includes('ℹ️') || (el.classList && el.classList.contains('info-icon'));
        const styleAttr = el.getAttribute ? (el.getAttribute('style') || '') : '';
        const hasHelpCursor = (el.classList && el.classList.contains('cursor-help')) || styleAttr.includes('cursor:help') || styleAttr.includes('cursor: help');
        const hasExplicitInfoData = el.hasAttribute && (el.hasAttribute('data-tooltip-info') || el.hasAttribute('data-metric-info'));

        return isInfoIcon || hasHelpCursor || hasExplicitInfoData;
    }

    function ensureTooltip() {
        if (!tooltipEl) {
            tooltipEl = document.getElementById('netdiag-custom-tooltip');
            if (!tooltipEl) {
                tooltipEl = document.createElement('div');
                tooltipEl.id = 'netdiag-custom-tooltip';
                tooltipEl.className = 'netdiag-custom-tooltip';
                tooltipEl.setAttribute('role', 'tooltip');
                tooltipEl.setAttribute('aria-hidden', 'true');
                document.body.appendChild(tooltipEl);
            }
        }
        return tooltipEl;
    }

    function formatTooltipContent(rawText) {
        if (!rawText) return '';
        let clean = rawText.trim();
        // Limpieza de formato para estilo idéntico a Imagen 1 (simple, esbelto, directo)
        clean = clean.replace(/\\(Atajo:\\s*([^)]+)\\)/g, '<kbd class="tooltip-kbd">$1</kbd>');
        return `<div class="tooltip-body">${clean}</div>`;
    }

    function positionTooltip(target, tip) {
        const rect = target.getBoundingClientRect();
        const tipRect = tip.getBoundingClientRect();
        const gap = 6;

        let top = rect.top - tipRect.height - gap;
        if (top < 8) {
            top = rect.bottom + gap;
        }

        let left = rect.left + (rect.width / 2) - (tipRect.width / 2);
        const margin = 8;
        if (left < margin) {
            left = margin;
        } else if (left + tipRect.width > window.innerWidth - margin) {
            left = window.innerWidth - tipRect.width - margin;
        }

        tip.style.top = Math.round(top) + 'px';
        tip.style.left = Math.round(left) + 'px';
    }

    function getTooltipText(el) {
        if (!el || el === document.body || el === document.documentElement) return null;
        if (el.tagName && el.tagName.toLowerCase() === 'iframe') return null;
        if (el.id === 'mainViewIframe' || (el.closest && el.closest('iframe, #mainViewIframe'))) return null;
        if (el.dataset && el.dataset.customTooltip) return el.dataset.customTooltip;
        if (el.dataset && el.dataset.tooltip) return el.dataset.tooltip;

        // Soporte e intercepción para SVG <title> hijo
        const svgTitle = el.querySelector ? el.querySelector('title') : null;
        if (svgTitle && svgTitle.textContent && svgTitle.textContent.trim()) {
            const t = svgTitle.textContent.trim();
            el.dataset.customTooltip = t;
            svgTitle.dataset.origText = t;
            svgTitle.textContent = ''; // Vaciar para impedir el tooltip nativo del SO
            return t;
        }
        if (el.parentElement && ['circle', 'rect', 'path', 'polygon'].includes(el.tagName.toLowerCase())) {
            const pTitle = el.parentElement.querySelector ? el.parentElement.querySelector('title') : null;
            if (pTitle && pTitle.textContent && pTitle.textContent.trim()) {
                const t = pTitle.textContent.trim();
                el.dataset.customTooltip = t;
                pTitle.dataset.origText = t;
                pTitle.textContent = '';
                return t;
            }
        }

        // Atributo estándar title
        if (el.getAttribute && el.getAttribute('title')) {
            const t = el.getAttribute('title');
            if (t && t.trim()) {
                el.dataset.customTooltip = t.trim();
                el.setAttribute('aria-label', t.trim());
                el.removeAttribute('title'); // Neutralizar tooltip nativo del navegador
                return el.dataset.customTooltip;
            }
        }

        return null;
    }

    function showTooltip(target, text) {
        clearTimeout(hideTimer);
        clearTimeout(showTimer);
        const tip = ensureTooltip();
        tip.innerHTML = formatTooltipContent(text);
        tip.style.display = 'block';

        // Gestión obligatoria y robusta de pérdida de foco (mouseleave / pointerleave)
        function onTargetLeave() {
            hideTooltip();
            if (currentTarget === target) {
                currentTarget = null;
            }
            target.removeEventListener('mouseleave', onTargetLeave);
            target.removeEventListener('pointerleave', onTargetLeave);
        }
        target.addEventListener('mouseleave', onTargetLeave, { once: true });
        target.addEventListener('pointerleave', onTargetLeave, { once: true });

        showTimer = setTimeout(() => {
            if (currentTarget === target) {
                positionTooltip(target, tip);
                requestAnimationFrame(() => {
                    tip.classList.add('tooltip-visible');
                    tip.setAttribute('aria-hidden', 'false');
                });
            }
        }, 25);
    }

    function hideTooltip() {
        clearTimeout(showTimer);
        clearTimeout(hideTimer);
        if (!tooltipEl) return;
        tooltipEl.classList.remove('tooltip-visible');
        tooltipEl.setAttribute('aria-hidden', 'true');
        tooltipEl.style.display = 'none';
    }

    function findEligibleTarget(rawTarget) {
        if (!rawTarget) return null;
        // Si el elemento o su padre es un elemento SVG con <title>
        if (rawTarget.tagName && ['circle', 'rect', 'path', 'polygon', 'g'].includes(rawTarget.tagName.toLowerCase())) {
            const hasT = (rawTarget.querySelector && rawTarget.querySelector('title')) || (rawTarget.parentElement && rawTarget.parentElement.querySelector && rawTarget.parentElement.querySelector('title'));
            if (hasT || rawTarget.dataset?.customTooltip || rawTarget.getAttribute('title')) {
                return rawTarget;
            }
        }
        return rawTarget.closest ? rawTarget.closest(CANDIDATE_SELECTOR) : null;
    }

    document.addEventListener('mouseover', function(e) {
        const target = findEligibleTarget(e.target);
        if (!target || !isEligibleForTooltip(target)) {
            if (currentTarget) {
                hideTooltip();
                currentTarget = null;
            }
            if (target && target.getAttribute && target.getAttribute('title')) {
                const nativeTitle = target.getAttribute('title');
                if (nativeTitle && nativeTitle.trim()) {
                    target.setAttribute('aria-label', nativeTitle.trim());
                    target.removeAttribute('title');
                }
            }
            return;
        }

        if (currentTarget === target) return;

        if (currentTarget && currentTarget !== target) {
            hideTooltip();
        }

        const text = getTooltipText(target);
        if (!text) {
            hideTooltip();
            currentTarget = null;
            return;
        }

        currentTarget = target;
        showTooltip(target, text);
    }, true);

    document.addEventListener('mouseout', function(e) {
        if (currentTarget) {
            if (!e.relatedTarget || (e.target === currentTarget && !currentTarget.contains(e.relatedTarget)) || (!currentTarget.contains(e.relatedTarget))) {
                hideTooltip();
                currentTarget = null;
            }
        }
    }, true);

    document.documentElement.addEventListener('mouseleave', function() {
        hideTooltip();
        currentTarget = null;
    });

    window.addEventListener('blur', function() {
        hideTooltip();
        currentTarget = null;
    });

    document.addEventListener('pointerdown', function() {
        hideTooltip();
        currentTarget = null;
    }, true);

    window.addEventListener('scroll', function() {
        hideTooltip();
        currentTarget = null;
    }, { passive: true });

    document.addEventListener('keydown', function(ev) {
        if (ev.key === 'Escape') {
            hideTooltip();
            currentTarget = null;
        }
    });

    document.addEventListener('visibilitychange', function() {
        if (document.hidden) {
            hideTooltip();
            currentTarget = null;
        }
    });
})();
</script>
"""
