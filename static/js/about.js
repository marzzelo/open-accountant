/* about.js — Open Accountant · Developer About panel */
'use strict';

const About = {
  async render() {
    const main = document.getElementById('main');
    main.innerHTML = `<div class="flex items-center justify-center h-full">
      <div class="text-dark-500 text-sm animate-pulse">Loading…</div></div>`;

    let data;
    try {
      data = await API.get('/about');
    } catch (e) {
      main.innerHTML = `
        <div class="flex items-center justify-center h-full p-8">
          <div class="bg-dark-800 border border-red-900/40 rounded-2xl p-8 max-w-md w-full text-center">
            <div class="text-3xl mb-3">⚠️</div>
            <p class="text-red-400 text-sm">${t('about.tampered')}</p>
          </div>
        </div>`;
      return;
    }

    main.innerHTML = `
      <div class="overflow-y-auto flex-1 flex items-center justify-center p-8">
        <div class="bg-dark-800 border border-dark-600 rounded-2xl p-8 max-w-lg w-full shadow-2xl">

          <!-- Header -->
          <div class="flex items-center gap-4 mb-8 pb-6 border-b border-dark-700">
            <div class="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-600/30 to-blue-900/40
                        border border-blue-500/30 flex items-center justify-center text-3xl shrink-0">
              💰
            </div>
            <div>
              <h1 class="text-xl font-bold text-dark-100">${data.version}</h1>
              <p class="text-xs text-dark-500 mt-0.5">Double-entry personal accounting · MIT License</p>
              <div class="flex items-center gap-1.5 mt-1.5">
                <span class="w-1.5 h-1.5 rounded-full bg-green-500 inline-block"></span>
                <span class="text-[10px] text-green-400 font-mono">integrity verified ✓</span>
              </div>
            </div>
          </div>

          <!-- Dev card -->
          <div class="space-y-5">

            <div class="flex items-start gap-4">
              <div class="w-8 h-8 rounded-lg bg-blue-600/15 border border-blue-500/20
                          flex items-center justify-center text-base shrink-0 mt-0.5">👤</div>
              <div>
                <p class="text-[10px] text-dark-500 uppercase tracking-widest mb-0.5">${t('about.dev')}</p>
                <p class="text-dark-100 font-semibold">${data.name}</p>
              </div>
            </div>

            <div class="flex items-start gap-4">
              <div class="w-8 h-8 rounded-lg bg-blue-600/15 border border-blue-500/20
                          flex items-center justify-center text-base shrink-0 mt-0.5">✉️</div>
              <div>
                <p class="text-[10px] text-dark-500 uppercase tracking-widest mb-0.5">Email</p>
                <a href="mailto:${data.email}"
                   class="text-blue-400 hover:text-blue-300 text-sm font-mono transition-colors">
                  ${data.email}
                </a>
              </div>
            </div>

            <div class="flex items-start gap-4">
              <div class="w-8 h-8 rounded-lg bg-blue-600/15 border border-blue-500/20
                          flex items-center justify-center text-base shrink-0 mt-0.5">🏭</div>
              <div>
                <p class="text-[10px] text-dark-500 uppercase tracking-widest mb-0.5">${t('about.org')}</p>
                <p class="text-dark-300 text-sm leading-relaxed whitespace-pre-line">${data.org}</p>
              </div>
            </div>

            <div class="flex items-start gap-4">
              <div class="w-8 h-8 rounded-lg bg-blue-600/15 border border-blue-500/20
                          flex items-center justify-center text-base shrink-0 mt-0.5">
                <svg class="w-4 h-4 text-dark-300" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57
                           0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41
                           -1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815
                           2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925
                           0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23
                           .96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65
                           .24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925
                           .435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57
                           A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/>
                </svg>
              </div>
              <div>
                <p class="text-[10px] text-dark-500 uppercase tracking-widest mb-0.5">${t('about.source')}</p>
                <a href="${data.github}" target="_blank" rel="noopener"
                   class="text-blue-400 hover:text-blue-300 text-sm font-mono transition-colors">
                  ${data.github.replace('https://','')}
                </a>
              </div>
            </div>

          </div>

          <!-- Footer -->
          <div class="mt-8 pt-6 border-t border-dark-700 flex items-center justify-between">
            <span class="text-[10px] text-dark-600">© ${data.year} ${data.name}</span>
            <span class="text-[10px] text-dark-600 font-mono">
              <span class="text-green-600">●</span> HMAC-SHA256 sealed
            </span>
          </div>

        </div>
      </div>`;
  },
};
