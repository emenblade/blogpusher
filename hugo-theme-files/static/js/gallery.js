/**
 * static/js/gallery.js
 * ──────────────────────────────────────────────────────────────────────────────
 * Gallery slider + lightbox for hugo-mana-theme.
 * Uses the same init pattern as all other Mana theme JS files.
 */

/**
 * Initialize gallery slider and lightbox
 */
function initGallery() {
  const slider    = document.getElementById('gallery-slider');
  const track     = document.getElementById('gallery-track');
  const dotsWrap  = document.getElementById('gallery-dots');
  const prevBtn   = document.getElementById('gallery-prev');
  const nextBtn   = document.getElementById('gallery-next');
  const counter   = document.getElementById('gallery-current');
  const expandBtn = document.getElementById('gallery-expand');
  const lightbox  = document.getElementById('gallery-lightbox');
  const lbImg     = document.getElementById('lb-img');
  const lbCaption = document.getElementById('lb-caption');
  const lbClose   = document.getElementById('lb-close');
  const lbPrev    = document.getElementById('lb-prev');
  const lbNext    = document.getElementById('lb-next');

  // Nothing to do if there's no gallery on this page
  if (!slider || !track) return;

  // Skip if already initialized (guards against double-init)
  if (slider.dataset.initialized === 'true') return;
  slider.dataset.initialized = 'true';

  /* ── State ──────────────────────────────────────────────────────────── */
  const slides = Array.from(track.querySelectorAll('.gallery-slide'));
  const dots   = dotsWrap ? Array.from(dotsWrap.querySelectorAll('.gallery-dot')) : [];
  const total  = slides.length;
  let current  = 0;
  let isLightboxOpen = false;

  /* ── Go to slide N ──────────────────────────────────────────────────── */
  function goTo(n) {
    n = Math.max(0, Math.min(n, total - 1));
    current = n;

    track.style.transform = `translateX(-${current * 100}%)`;

    slides.forEach((s, i) => s.setAttribute('aria-hidden', i !== current));

    dots.forEach((d, i) => {
      d.classList.toggle('active', i === current);
      d.setAttribute('aria-selected', i === current);
    });

    if (counter) counter.textContent = current + 1;
    if (prevBtn) prevBtn.disabled = current === 0;
    if (nextBtn) nextBtn.disabled = current === total - 1;

    if (isLightboxOpen) syncLightbox(current);
  }

  /* ── Controls ───────────────────────────────────────────────────────── */
  if (prevBtn) prevBtn.addEventListener('click', () => goTo(current - 1));
  if (nextBtn) nextBtn.addEventListener('click', () => goTo(current + 1));

  dots.forEach(dot => {
    dot.addEventListener('click', () => goTo(parseInt(dot.dataset.index, 10)));
  });

  /* ── Keyboard ───────────────────────────────────────────────────────── */
  document.addEventListener('keydown', e => {
    if (!slider || !document.contains(slider)) return;
    if (!isLightboxOpen && !slider.matches(':focus-within') &&
        document.activeElement !== document.body) return;

    if (e.key === 'ArrowLeft')  { e.preventDefault(); goTo(current - 1); }
    if (e.key === 'ArrowRight') { e.preventDefault(); goTo(current + 1); }
    if (e.key === 'Escape' && isLightboxOpen) closeLightbox();
  });

  /* ── Drag (mouse) ───────────────────────────────────────────────────── */
  let dragStartX = null;
  let isDragging = false;

  track.addEventListener('mousedown', e => {
    dragStartX = e.clientX;
    isDragging = false;
    track.style.transition = 'none';
  });

  window.addEventListener('mousemove', e => {
    if (dragStartX === null) return;
    if (Math.abs(e.clientX - dragStartX) > 5) isDragging = true;
  });

  window.addEventListener('mouseup', e => {
    if (dragStartX === null) return;
    track.style.transition = '';
    const diff = e.clientX - dragStartX;
    dragStartX = null;
    if (Math.abs(diff) > 50) {
      goTo(diff < 0 ? current + 1 : current - 1);
    } else {
      goTo(current);
    }
    if (isDragging) { e.stopPropagation(); isDragging = false; }
  });

  /* ── Touch / swipe ──────────────────────────────────────────────────── */
  let touchStartX = null;
  let touchStartY = null;

  track.addEventListener('touchstart', e => {
    touchStartX = e.changedTouches[0].screenX;
    touchStartY = e.changedTouches[0].screenY;
  }, { passive: true });

  track.addEventListener('touchend', e => {
    if (touchStartX === null) return;
    const dx = e.changedTouches[0].screenX - touchStartX;
    const dy = e.changedTouches[0].screenY - touchStartY;
    if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 40) {
      goTo(dx < 0 ? current + 1 : current - 1);
    }
    touchStartX = touchStartY = null;
  }, { passive: true });

  /* ── Lightbox helpers ───────────────────────────────────────────────── */
  function getImageData(index) {
    const slide = slides[index];
    if (!slide) return { src: '', alt: '', caption: '' };
    const img = slide.querySelector('img');
    const cap = slide.querySelector('.gallery-slide-caption');
    return {
      src:     img ? img.src : '',
      alt:     img ? img.alt : '',
      caption: cap ? cap.textContent.trim() : (img ? img.alt : ''),
    };
  }

  function syncLightbox(index) {
    const { src, alt, caption } = getImageData(index);
    lbImg.classList.add('is-swapping');
    setTimeout(() => {
      lbImg.src = src;
      lbImg.alt = alt;
      lbCaption.textContent = caption;
      lbImg.classList.remove('is-swapping');
    }, 150);
    if (lbPrev) lbPrev.disabled = index === 0;
    if (lbNext) lbNext.disabled = index === total - 1;
  }

  function openLightbox(index) {
    goTo(index);
    const { src, alt, caption } = getImageData(index);
    lbImg.src = src;
    lbImg.alt = alt;
    lbCaption.textContent = caption;
    if (lbPrev) lbPrev.disabled = index === 0;
    if (lbNext) lbNext.disabled = index === total - 1;

    lightbox.removeAttribute('hidden');
    requestAnimationFrame(() =>
      requestAnimationFrame(() => lightbox.classList.add('is-open'))
    );
    document.body.style.overflow = 'hidden';
    isLightboxOpen = true;
    if (lbClose) lbClose.focus();
    trapFocus(lightbox);
  }

  function closeLightbox() {
    lightbox.classList.remove('is-open');
    lightbox.addEventListener('transitionend', function h() {
      lightbox.setAttribute('hidden', '');
      lightbox.removeEventListener('transitionend', h);
    });
    document.body.style.overflow = '';
    isLightboxOpen = false;
    if (expandBtn) expandBtn.focus();
  }

  /* ── Lightbox controls ──────────────────────────────────────────────── */
  if (expandBtn) expandBtn.addEventListener('click', () => openLightbox(current));

  slides.forEach((slide, i) => {
    slide.setAttribute('tabindex', '0');
    slide.setAttribute('role', 'button');
    slide.setAttribute('aria-label', `View photo ${i + 1} of ${total} fullscreen`);
    slide.addEventListener('click', e => {
      if (isDragging) return;
      openLightbox(i);
    });
    slide.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openLightbox(i); }
    });
  });

  if (lbClose) lbClose.addEventListener('click', closeLightbox);
  if (lbPrev)  lbPrev.addEventListener('click',  () => { goTo(current - 1); syncLightbox(current); });
  if (lbNext)  lbNext.addEventListener('click',  () => { goTo(current + 1); syncLightbox(current); });

  lightbox.addEventListener('click', e => {
    if (e.target === lightbox) closeLightbox();
  });

  // Lightbox touch swipe
  let lbTouchX = null;
  lightbox.addEventListener('touchstart', e => { lbTouchX = e.changedTouches[0].screenX; }, { passive: true });
  lightbox.addEventListener('touchend',   e => {
    if (lbTouchX === null) return;
    const dx = e.changedTouches[0].screenX - lbTouchX;
    lbTouchX = null;
    if (Math.abs(dx) > 50) { goTo(dx < 0 ? current + 1 : current - 1); syncLightbox(current); }
  }, { passive: true });

  /* ── Focus trap ─────────────────────────────────────────────────────── */
  function trapFocus(container) {
    const focusable = container.querySelectorAll(
      'button:not(:disabled), [href], [tabindex]:not([tabindex="-1"])'
    );
    const first = focusable[0];
    const last  = focusable[focusable.length - 1];
    function handler(e) {
      if (e.key !== 'Tab') return;
      if (!isLightboxOpen) { container.removeEventListener('keydown', handler); return; }
      if (e.shiftKey) {
        if (document.activeElement === first) { e.preventDefault(); last.focus(); }
      } else {
        if (document.activeElement === last)  { e.preventDefault(); first.focus(); }
      }
    }
    container.addEventListener('keydown', handler);
  }

  /* ── Init ───────────────────────────────────────────────────────────── */
  goTo(0);
}

// ── Same init pattern used by every Mana theme JS file ──────────────────────
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initGallery);
} else {
  initGallery();
}
