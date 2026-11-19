// "Add to Home Screen" helper for iOS Safari.
//
// iOS Safari offers no install prompt and a web page cannot trigger
// "Add to Home Screen" itself. This module adds a small visible button
// that opens a short guide for the three taps Safari requires:
// Share -> "Add to Home Screen" -> Add. The button stays hidden when
// the site is already running as an installed (standalone) web app.
// The web app manifest (public/manifest.webmanifest) and the
// apple-touch-icon / apple-mobile-web-app-* tags in index.html provide
// the name, globe icon and standalone display the installed app uses.

if (typeof document !== 'undefined') {
  const isStandalone =
    (typeof window.matchMedia === 'function' &&
      window.matchMedia('(display-mode: standalone)').matches) ||
    window.navigator?.standalone === true;

  if (!isStandalone) {
    const shareIcon =
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 15V3"/><path d="m7 8 5-5 5 5"/><path d="M5 12v8a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-8"/></svg>';

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'gev-install-button';
    button.setAttribute('aria-haspopup', 'dialog');
    button.setAttribute('aria-controls', 'gev-install-guide');
    button.setAttribute('aria-expanded', 'false');
    button.innerHTML =
      '<span class="gev-install-button__icon" aria-hidden="true">' +
      shareIcon +
      '</span>' +
      '<span class="gev-install-button__label">Add to Home Screen</span>';

    const overlay = document.createElement('div');
    overlay.className = 'gev-install-overlay';
    overlay.id = 'gev-install-guide';
    overlay.hidden = true;
    overlay.innerHTML =
      '<div class="gev-install-card" role="dialog" aria-modal="true" aria-labelledby="gev-install-title">' +
      '<p class="gev-install-card__eyebrow">iPhone &middot; Safari</p>' +
      '<h2 class="gev-install-card__title" id="gev-install-title">Add to Home Screen</h2>' +
      '<p class="gev-install-card__intro">Safari doesn&rsquo;t let a website add itself to your Home Screen, but it only takes three taps:</p>' +
      '<ol class="gev-install-steps">' +
      '<li><span class="gev-install-steps__icon" aria-hidden="true">' +
      shareIcon +
      '</span><span>Tap the <strong>Share</strong> button (the square with an arrow pointing up) in Safari&rsquo;s toolbar.</span></li>' +
      '<li><span class="gev-install-steps__num" aria-hidden="true">2</span><span>Scroll down and tap <strong>&ldquo;Add to Home Screen&rdquo;</strong>.</span></li>' +
      '<li><span class="gev-install-steps__num" aria-hidden="true">3</span><span>Tap <strong>Add</strong> in the top-right corner.</span></li>' +
      '</ol>' +
      '<p class="gev-install-card__note">God&rsquo;s Eye View will then open full-screen from your Home Screen, just like an app. On Android or desktop Chrome, use your browser&rsquo;s menu instead and choose &ldquo;Install app&rdquo;.</p>' +
      '<button type="button" class="gev-install-card__close">Got it</button>' +
      '</div>';

    const closeButton = overlay.querySelector('.gev-install-card__close');

    function openGuide() {
      overlay.hidden = false;
      button.setAttribute('aria-expanded', 'true');
      if (closeButton) closeButton.focus();
    }

    function closeGuide() {
      overlay.hidden = true;
      button.setAttribute('aria-expanded', 'false');
      button.focus();
    }

    button.addEventListener('click', openGuide);
    if (closeButton) closeButton.addEventListener('click', closeGuide);
    overlay.addEventListener('click', (event) => {
      if (event.target === overlay) closeGuide();
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && !overlay.hidden) closeGuide();
    });

    document.body.append(button, overlay);
  }
}
