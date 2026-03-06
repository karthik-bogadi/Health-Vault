/* ============================================================
   HEALTH VAULT — script.js
   Vanilla JS only. No frameworks.
   ============================================================ */

/* ── Theme Toggle ───────────────────────────────────────────
   Reads / writes localStorage key 'hv-theme' ('dark' | 'light').
   Sets data-theme attribute on <html> — CSS vars do the rest.
   ────────────────────────────────────────────────────────── */
   (function () {
    var STORAGE_KEY = 'hv-theme';
    var html        = document.documentElement;
  
    function applyTheme(theme) {
      if (theme === 'dark') {
        html.setAttribute('data-theme', 'dark');
      } else {
        html.removeAttribute('data-theme');
      }
      localStorage.setItem(STORAGE_KEY, theme);
    }
  
    function currentTheme() {
      return html.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
    }
  
    // Wire up button once DOM is ready
    document.addEventListener('DOMContentLoaded', function () {
      var btn = document.getElementById('theme-toggle');
      if (!btn) return;
  
      btn.addEventListener('click', function () {
        var next = currentTheme() === 'dark' ? 'light' : 'dark';
        applyTheme(next);
  
        // Brief spin animation on the button for tactile feedback
        btn.style.transform = 'rotate(20deg) scale(0.9)';
        setTimeout(function () { btn.style.transform = ''; }, 180);
      });
    });
  })();
  
  document.addEventListener('DOMContentLoaded', function () {
  
    /* ── Staggered card animations ──────────────────────────── */
    const animatables = document.querySelectorAll(
      '.card, .feature-card, .reports-card, .key-card, .emergency-card, .upload-card, .doctor-reports-card'
    );
    animatables.forEach(function (el, i) {
      el.style.animationDelay = (i * 0.06) + 's';
    });
  
    /* ── File input label update ────────────────────────────── */
    const fileInput = document.getElementById('report_file');
    const fileChosen = document.getElementById('file-chosen-label');
  
    if (fileInput && fileChosen) {
      fileInput.addEventListener('change', function () {
        if (fileInput.files && fileInput.files.length > 0) {
          const name = fileInput.files[0].name;
          const size = (fileInput.files[0].size / 1024).toFixed(1);
          fileChosen.innerHTML =
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>' +
            name + ' <span style="color:var(--text-muted)">(' + size + ' KB)</span>';
          fileChosen.style.borderColor = 'var(--blue-500)';
          fileChosen.style.color = 'var(--text-primary)';
          fileChosen.style.background = 'var(--blue-50)';
        }
      });
    }
  
    /* ── Drag-over highlight on upload card ─────────────────── */
    const uploadCard = document.querySelector('.upload-card');
    if (uploadCard && fileInput) {
      uploadCard.addEventListener('dragover', function (e) {
        e.preventDefault();
        uploadCard.classList.add('dragover');
      });
      uploadCard.addEventListener('dragleave', function () {
        uploadCard.classList.remove('dragover');
      });
      uploadCard.addEventListener('drop', function (e) {
        e.preventDefault();
        uploadCard.classList.remove('dragover');
        if (e.dataTransfer.files.length) {
          fileInput.files = e.dataTransfer.files;
          fileInput.dispatchEvent(new Event('change'));
        }
      });
    }
  
    /* ── Select-all reports checkbox ───────────────────────── */
    const selectAll = document.getElementById('select_all_reports');
    if (selectAll) {
      selectAll.addEventListener('change', function () {
        document.querySelectorAll('.report-checkbox').forEach(function (box) {
          box.checked = selectAll.checked;
        });
      });
  
      // Update select-all state when individual boxes change
      document.querySelectorAll('.report-checkbox').forEach(function (box) {
        box.addEventListener('change', function () {
          const all  = document.querySelectorAll('.report-checkbox');
          const checked = document.querySelectorAll('.report-checkbox:checked');
          selectAll.indeterminate = checked.length > 0 && checked.length < all.length;
          selectAll.checked = checked.length === all.length;
        });
      });
    }
  
    /* ── Copy access key to clipboard ──────────────────────── */
    const copyBtn = document.getElementById('copy-key-btn');
    const keyValueEl = document.getElementById('key-display-value');
  
    if (copyBtn && keyValueEl) {
      copyBtn.addEventListener('click', function () {
        const text = keyValueEl.textContent.trim();
        navigator.clipboard.writeText(text).then(function () {
          copyBtn.textContent = '✓ Copied!';
          copyBtn.style.background = 'rgba(16,185,129,0.2)';
          copyBtn.style.color = '#6ee7b7';
          copyBtn.style.borderColor = 'rgba(16,185,129,0.3)';
          setTimeout(function () {
            copyBtn.textContent = 'Copy';
            copyBtn.style.background = '';
            copyBtn.style.color = '';
            copyBtn.style.borderColor = '';
          }, 2000);
        }).catch(function () {
          // Fallback for older browsers
          const range = document.createRange();
          range.selectNode(keyValueEl);
          window.getSelection().removeAllRanges();
          window.getSelection().addRange(range);
          document.execCommand('copy');
          window.getSelection().removeAllRanges();
          copyBtn.textContent = '✓ Copied!';
          setTimeout(function () { copyBtn.textContent = 'Copy'; }, 2000);
        });
      });
    }
  
    /* ── Generate key loading state ────────────────────────── */
    const generateKeyForm = document.getElementById('generate-key-form');
    if (generateKeyForm) {
      generateKeyForm.addEventListener('submit', function () {
        const btn = generateKeyForm.querySelector('button[type="submit"]');
        if (btn) {
          btn.classList.add('loading');
          btn.disabled = true;
        }
      });
    }
  
    /* ── Upload form loading state ──────────────────────────── */
    const uploadForm = document.getElementById('upload-form');
    if (uploadForm) {
      uploadForm.addEventListener('submit', function () {
        const btn = uploadForm.querySelector('button[type="submit"]');
        if (btn) {
          btn.classList.add('loading');
          btn.disabled = true;
          btn.textContent = 'Uploading';
        }
      });
    }
  
    /* ── Doctor form loading state ──────────────────────────── */
    const doctorForm = document.getElementById('doctor-form');
    if (doctorForm) {
      doctorForm.addEventListener('submit', function () {
        const btn = doctorForm.querySelector('button[type="submit"]');
        if (btn) {
          btn.classList.add('loading');
          btn.disabled = true;
        }
      });
    }
  
    /* ── Auto-dismiss flash messages ───────────────────────── */
    const flashes = document.querySelectorAll('.flash');
    flashes.forEach(function (flash) {
      setTimeout(function () {
        flash.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
        flash.style.opacity = '0';
        flash.style.transform = 'translateY(-6px)';
        setTimeout(function () {
          if (flash.parentNode) flash.parentNode.removeChild(flash);
        }, 400);
      }, 4000);
    });
  
    /* ── Report icon helper (assign correct icon class) ──── */
    document.querySelectorAll('.report-icon[data-filename]').forEach(function (el) {
      const name = (el.getAttribute('data-filename') || '').toLowerCase();
      if (name.endsWith('.pdf')) {
        el.classList.add('icon-pdf');
        el.textContent = 'PDF';
      } else if (name.match(/\.(png|jpg|jpeg|gif|webp)$/)) {
        el.classList.add('icon-img');
        el.textContent = 'IMG';
      } else {
        el.classList.add('icon-file');
        el.textContent = 'DOC';
      }
    });
  
    /* ── AI Summary Feature ─────────────────────────────────── */
    async function generateSummary(reportId, btn) {
      const statusEl = document.getElementById('ai-status-' + reportId);
      if (statusEl) statusEl.textContent = 'Generating summary…';
      if (btn) { btn.disabled = true; btn.textContent = 'Generating…'; }
  
      const url = '/summarize/' + reportId;
      try {
        const res  = await fetch(url, { method: 'GET' });
        const data = await res.json();
  
        if (statusEl) statusEl.textContent = '';
        if (btn) { btn.disabled = false; btn.innerHTML = sparkIcon() + 'AI Summary'; }
  
        displayAISummary(res.ok ? (data.summary || 'No summary returned.') : (data.error || 'Failed to generate summary.'));
      } catch (err) {
        if (statusEl) statusEl.textContent = '';
        if (btn) { btn.disabled = false; btn.innerHTML = sparkIcon() + 'AI Summary'; }
        displayAISummary('Network error while generating summary.');
      }
    }
  
    function sparkIcon() {
      return '<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 17l-6.2 4.3 2.4-7.4L2 9.4h7.6z"/></svg>';
    }
  
    function displayAISummary(summaryText) {
      const container = document.getElementById('aiSummaryContainer');
      if (!container) return;
  
      const card = document.createElement('div');
      card.className = 'ai-summary-card';
  
      const header = document.createElement('div');
      header.className = 'ai-summary-header';
      header.innerHTML =
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 17l-6.2 4.3 2.4-7.4L2 9.4h7.6z"/></svg>' +
        'AI Analysis Result';
  
      const pre = document.createElement('pre');
      pre.className = 'summary-text';
      pre.textContent = summaryText;
  
      card.appendChild(header);
      card.appendChild(pre);
      container.prepend(card);
  
      // Make sure section is visible
      const section = document.querySelector('.ai-summary-section');
      if (section) section.style.display = '';
    }
  
    document.querySelectorAll('.ai-summary-btn').forEach(function (btn) {
      btn.innerHTML = sparkIcon() + 'AI Summary';
      btn.addEventListener('click', function () {
        const reportId = btn.getAttribute('data-report-id');
        if (reportId) generateSummary(reportId, btn);
      });
    });
  
    /* ── Input focus enhancement ────────────────────────────── */
    document.querySelectorAll('input, textarea').forEach(function (el) {
      el.addEventListener('focus', function () {
        el.closest('.form-group') && el.closest('.form-group').classList.add('focused');
      });
      el.addEventListener('blur', function () {
        el.closest('.form-group') && el.closest('.form-group').classList.remove('focused');
      });
    });
  
    /* ── Access Key Countdown Timer ─────────────────────────────
       Reads data-expiry="YYYY-MM-DD HH:MM:SS" from #countdown-banner.
       Ticks every second. Transitions through three visual states:
         1. Normal  (> 2 min left)  — green/teal banner
         2. Warning (≤ 2 min left)  — amber banner, warning icon
         3. Expired (≤ 0 sec left)  — red banner, reports overlaid
    ────────────────────────────────────────────────────────── */
    (function initCountdown() {
      var banner = document.getElementById('countdown-banner');
      if (!banner) return;   // Not on doctor page or no active key
  
      // ── Parse expiry timestamp from template ────────────────
      var rawExpiry = banner.getAttribute('data-expiry') || '';
      // Flask renders "2026-03-05 22:12:12" — replace space with T for
      // universal Date() parsing (avoids Safari/Firefox quirks)
      var expiryDate = new Date(rawExpiry.replace(' ', 'T'));
  
      if (isNaN(expiryDate.getTime())) {
        // Unparseable timestamp — hide the banner silently
        banner.style.display = 'none';
        return;
      }
  
      // ── DOM references ──────────────────────────────────────
      var mmEl          = document.getElementById('countdown-mm');
      var ssEl          = document.getElementById('countdown-ss');
      var labelEl       = document.getElementById('countdown-label');
      var sublabelEl    = document.getElementById('countdown-sublabel');
      var progressBar   = document.getElementById('countdown-progress-bar');
      var clockIcon     = document.getElementById('countdown-clock-icon');
      var warnIcon      = document.getElementById('countdown-warn-icon');
      var reportsCard   = document.getElementById('reports-card');
      var expiredOverlay= document.getElementById('expired-overlay');
  
      // Total key lifetime (15 min = 900 s) — used to scale progress bar
      var TOTAL_SECONDS = 15 * 60;
  
      // ── Helpers ─────────────────────────────────────────────
      function pad(n) {
        return String(Math.max(0, n)).padStart(2, '0');
      }
  
      function getRemainingSeconds() {
        return Math.floor((expiryDate.getTime() - Date.now()) / 1000);
      }
  
      // ── State: Warning (≤ 2 min) ───────────────────────────
      function applyWarningState() {
        banner.classList.remove('countdown-active');
        banner.classList.add('countdown-warning');
        clockIcon.style.display = 'none';
        warnIcon.style.display  = 'block';
        labelEl.textContent     = 'Key expiring soon';
        sublabelEl.textContent  = 'Save your work — access ends shortly';
      }
  
      // ── State: Expired ──────────────────────────────────────
      function applyExpiredState() {
        // Banner → red expired style
        banner.classList.remove('countdown-active', 'countdown-warning');
        banner.classList.add('countdown-expired');
        clockIcon.style.display = 'none';
        warnIcon.style.display  = 'none';
        labelEl.textContent     = 'Access key expired';
        sublabelEl.textContent  = 'Ask the patient to generate a new key';
        mmEl.textContent        = 'EX';
        ssEl.textContent        = 'PD';
  
        // Freeze progress bar at zero
        if (progressBar) progressBar.style.width = '0%';
  
        // Show expired overlay over the reports card
        if (reportsCard)    reportsCard.classList.add('reports-expired');
        if (expiredOverlay) expiredOverlay.style.display = 'flex';
      }
  
      // ── Tick function (runs every second) ───────────────────
      function tick() {
        var remaining = getRemainingSeconds();
  
        if (remaining <= 0) {
          clearInterval(timer);
          applyExpiredState();
          return;
        }
  
        // Calculate MM and SS
        var mins = Math.floor(remaining / 60);
        var secs = remaining % 60;
  
        // Update digits
        mmEl.textContent = pad(mins);
        ssEl.textContent = pad(secs);
  
        // Update progress bar width (shrinks from 100% → 0%)
        if (progressBar) {
          var pct = Math.min(100, (remaining / TOTAL_SECONDS) * 100);
          progressBar.style.width = pct + '%';
        }
  
        // Transition to warning state when ≤ 2 minutes remain
        if (remaining <= 120 && !banner.classList.contains('countdown-warning')) {
          applyWarningState();
        }
      }
  
      // ── Kickoff ─────────────────────────────────────────────
      // Run immediately so there's no 1-second blank delay
      tick();
  
      // Already expired before the page even loaded
      if (getRemainingSeconds() <= 0) return;
  
      var timer = setInterval(tick, 1000);
  
    })();
    /* ── End Countdown Timer ─────────────────────────────────── */
  
  
  /* ── Hero floating particles ────────────────────────────────
     Spawns small animated circles inside .hero-card for depth.
  ────────────────────────────────────────────────────────── */
  (function spawnHeroParticles() {
    var hero = document.querySelector('.hero-card');
    if (!hero) return;
    function spawn() {
      var p = document.createElement('span');
      p.className = 'hero-particle';
      var size = Math.random() * 18 + 6;
      var left = Math.random() * 90 + 5;
      var dur  = Math.random() * 6 + 5;
      var delay = Math.random() * 4;
      p.style.cssText =
        'width:' + size + 'px;height:' + size + 'px;' +
        'left:' + left + '%;bottom:-' + size + 'px;' +
        'animation-duration:' + dur + 's;' +
        'animation-delay:' + delay + 's;';
      hero.appendChild(p);
      setTimeout(function () { if (p.parentNode) p.parentNode.removeChild(p); }, (dur + delay) * 1000);
    }
    for (var i = 0; i < 6; i++) spawn();
    setInterval(spawn, 1800);
  })();

  /* ── Animated access key generation ────────────────────────
     When the generate-key form submits, adds .key-generating
     to the key-display div so the keyReveal CSS runs when
     the page reloads with a new key.
  ────────────────────────────────────────────────────────── */
  (function enhanceKeyGeneration() {
    var keyDisplay = document.querySelector('.key-display');
    if (keyDisplay) {
      // Page just loaded with a key — trigger reveal animation
      keyDisplay.classList.add('key-generating');
      setTimeout(function () { keyDisplay.classList.remove('key-generating'); }, 800);
    }

    var genForm = document.getElementById('generate-key-form');
    if (genForm) {
      genForm.addEventListener('submit', function () {
        var btn = genForm.querySelector('button[type="submit"]');
        if (!btn) return;
        // Animated generating state
        btn.innerHTML =
          '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="animation:spin 0.7s linear infinite">' +
          '<path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/></svg>' +
          ' Generating Key…';
        btn.disabled = true;
      });
    }
  })();

  /* ── Page transition on internal links ──────────────────────
     Adds a brief blue flash when navigating between pages.
  ────────────────────────────────────────────────────────── */
  (function pageTransition() {
    var overlay = document.createElement('div');
    overlay.className = 'page-transition-overlay';
    document.body.appendChild(overlay);

    document.querySelectorAll('a[href]').forEach(function (link) {
      var href = link.getAttribute('href');
      // Only internal links, not new-tab links, not anchors
      if (!href || href.startsWith('#') || href.startsWith('http') ||
          link.target === '_blank') return;

      link.addEventListener('click', function (e) {
        // Don't intercept if modifier keys are held
        if (e.metaKey || e.ctrlKey || e.shiftKey) return;
        overlay.classList.add('leaving');
        setTimeout(function () { overlay.classList.remove('leaving'); }, 300);
      });
    });
  })();

  /* ── Report icon — animate on appearance ────────────────────
     Each icon gets a pop-in entrance.
  ────────────────────────────────────────────────────────── */
  document.querySelectorAll('.report-icon[data-filename]').forEach(function (el, i) {
    el.style.opacity = '0';
    el.style.transform = 'scale(0.5)';
    setTimeout(function () {
      el.style.transition = 'opacity 0.25s ease, transform 0.3s cubic-bezier(0.34,1.56,0.64,1)';
      el.style.opacity = '1';
      el.style.transform = 'scale(1)';
    }, 60 + i * 40);
  });

  /* ── Copy button — enhanced feedback ────────────────────────
     Adds .copied class for CSS glow effect (in addition to text).
  ────────────────────────────────────────────────────────── */
  var copyBtnEl = document.getElementById('copy-key-btn');
  if (copyBtnEl) {
    var origCopyHandler = copyBtnEl.onclick;
    copyBtnEl.addEventListener('click', function () {
      copyBtnEl.classList.add('copied');
      setTimeout(function () { copyBtnEl.classList.remove('copied'); }, 2100);
    });
  }

  /* ── Number step hover class for how-it-works ───────────────
     Adds .how-step-num to the numbered circles so CSS can
     apply the bounce animation.
  ────────────────────────────────────────────────────────── */
  document.querySelectorAll('.dashboard-right [style*="border-radius:50%"]').forEach(function (el) {
    el.classList.add('how-step-num');
  });

  /* ── Tilt effect on feature cards ──────────────────────────
     Subtle 3-D tilt following mouse position on hover.
  ────────────────────────────────────────────────────────── */
  document.querySelectorAll('.feature-card').forEach(function (card) {
    card.addEventListener('mousemove', function (e) {
      var rect = card.getBoundingClientRect();
      var cx   = rect.left + rect.width  / 2;
      var cy   = rect.top  + rect.height / 2;
      var dx   = (e.clientX - cx) / (rect.width  / 2);
      var dy   = (e.clientY - cy) / (rect.height / 2);
      card.style.transform = 'translateY(-4px) rotateY(' + (dx * 4) + 'deg) rotateX(' + (-dy * 4) + 'deg)';
    });
    card.addEventListener('mouseleave', function () {
      card.style.transform = '';
      card.style.transition = 'transform 0.4s ease, box-shadow 0.25s ease, border-color 0.25s ease';
    });
    card.addEventListener('mouseenter', function () {
      card.style.transition = 'transform 0.1s ease, box-shadow 0.25s ease, border-color 0.25s ease';
    });
  });

  /* ── Key value number scramble on load ──────────────────────
     Scrambles the key characters then resolves to real value,
     giving a "decrypting" visual effect.
  ────────────────────────────────────────────────────────── */
  (function scrambleKey() {
    var keyEl = document.getElementById('key-display-value');
    if (!keyEl) return;

    var realText  = keyEl.textContent.trim();
    var chars     = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    var steps     = 10;
    var stepDelay = 55;
    var current   = 0;

    function scrambleStep() {
      if (current >= steps) { keyEl.textContent = realText; return; }
      var scrambled = realText.split('').map(function (ch, i) {
        // Lock characters in from left as we progress
        if (i < Math.floor((current / steps) * realText.length)) return ch;
        if (ch === '-' || ch === ' ') return ch;
        return chars[Math.floor(Math.random() * chars.length)];
      }).join('');
      keyEl.textContent = scrambled;
      current++;
      setTimeout(scrambleStep, stepDelay);
    }

    // Small delay so it's visible after page load
    setTimeout(scrambleStep, 300);
  })();

});