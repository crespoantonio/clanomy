// Clanomy Landing Page Interactive Script (Vanilla JS)

document.addEventListener('DOMContentLoaded', () => {
  let isAnnual = false;
  let currentLang = 'en';

  // 1. Billing Period Toggle (Monthly <-> Annual)
  const billingToggle = document.getElementById('billing-toggle');
  const monthlyLabel = document.getElementById('toggle-monthly-label');
  const annualLabel = document.getElementById('toggle-annual-label');
  const soloPrice = document.getElementById('solo-price');
  const soloPeriod = document.getElementById('solo-period');
  const duoPrice = document.getElementById('duo-price');
  const duoPeriod = document.getElementById('duo-period');
  const familyPrice = document.getElementById('family-price');
  const familyPeriod = document.getElementById('family-period');

  function updatePricing(annual) {
    isAnnual = annual;
    if (billingToggle) {
      billingToggle.classList.toggle('annual', isAnnual);
    }
    if (monthlyLabel && annualLabel) {
      monthlyLabel.classList.toggle('active', !isAnnual);
      annualLabel.classList.toggle('active', isAnnual);
    }

    const periodText = isAnnual
      ? (currentLang === 'es' ? '/ año' : '/ year')
      : (currentLang === 'es' ? '/ mes' : '/ month');

    if (soloPrice && soloPeriod) {
      soloPrice.textContent = isAnnual ? '49.99' : '4.99';
      soloPeriod.textContent = periodText;
    }
    if (duoPrice && duoPeriod) {
      duoPrice.textContent = isAnnual ? '79.99' : '7.99';
      duoPeriod.textContent = periodText;
    }
    if (familyPrice && familyPeriod) {
      familyPrice.textContent = isAnnual ? '119.99' : '11.99';
      familyPeriod.textContent = periodText;
    }
  }

  if (billingToggle) {
    billingToggle.addEventListener('click', () => {
      updatePricing(!isAnnual);
    });
  }

  if (monthlyLabel) {
    monthlyLabel.addEventListener('click', () => updatePricing(false));
  }

  if (annualLabel) {
    annualLabel.addEventListener('click', () => updatePricing(true));
  }

  // 2. Language Switcher (EN <-> ES)
  function setLanguage(lang) {
    if (typeof TRANSLATIONS === 'undefined' || !TRANSLATIONS[lang]) return;
    currentLang = lang;
    document.documentElement.lang = lang;

    const btnEn = document.getElementById('lang-btn-en');
    const btnEs = document.getElementById('lang-btn-es');
    if (btnEn && btnEs) {
      btnEn.classList.toggle('active', lang === 'en');
      btnEs.classList.toggle('active', lang === 'es');
    }

    document.querySelectorAll('[data-i18n]').forEach((el) => {
      const key = el.getAttribute('data-i18n');
      if (TRANSLATIONS[lang] && TRANSLATIONS[lang][key] !== undefined) {
        el.innerHTML = TRANSLATIONS[lang][key];
      }
    });

    // Update pricing period labels according to active language
    updatePricing(isAnnual);

    try {
      localStorage.setItem('clanomy_lang', lang);
    } catch (e) {
      // Ignore localStorage exceptions
    }
  }

  const btnEn = document.getElementById('lang-btn-en');
  const btnEs = document.getElementById('lang-btn-es');
  if (btnEn) {
    btnEn.addEventListener('click', () => setLanguage('en'));
  }
  if (btnEs) {
    btnEs.addEventListener('click', () => setLanguage('es'));
  }

  // Detect preferred language
  let savedLang = null;
  try {
    savedLang = localStorage.getItem('clanomy_lang');
  } catch (e) {}

  if (!savedLang && navigator.language && navigator.language.startsWith('es')) {
    savedLang = 'es';
  }

  if (savedLang && savedLang === 'es') {
    setLanguage('es');
  } else {
    setLanguage('en');
  }

  // 3. FAQ Accordion
  const faqQuestions = document.querySelectorAll('.faq-question');
  faqQuestions.forEach((button) => {
    button.addEventListener('click', () => {
      const isExpanded = button.getAttribute('aria-expanded') === 'true';
      const answer = button.nextElementSibling;

      // Close all other FAQs
      faqQuestions.forEach((otherButton) => {
        if (otherButton !== button) {
          otherButton.setAttribute('aria-expanded', 'false');
          otherButton.classList.remove('active');
          if (otherButton.nextElementSibling) {
            otherButton.nextElementSibling.classList.remove('show');
          }
        }
      });

      // Toggle current FAQ
      button.setAttribute('aria-expanded', !isExpanded);
      button.classList.toggle('active', !isExpanded);
      if (answer) {
        answer.classList.toggle('show', !isExpanded);
      }
    });
  });

  // 4. Legal Modals (Terms, Privacy, Refund)
  const modalTriggers = document.querySelectorAll('.modal-trigger');
  const modals = document.querySelectorAll('.modal');
  const closeButtons = document.querySelectorAll('.modal-close');

  function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.add('active');
      modal.setAttribute('aria-hidden', 'false');
      document.body.style.overflow = 'hidden'; // Prevent background scrolling
    }
  }

  function closeModal(modal) {
    if (modal) {
      modal.classList.remove('active');
      modal.setAttribute('aria-hidden', 'true');
      document.body.style.overflow = '';
    }
  }

  modalTriggers.forEach((trigger) => {
    trigger.addEventListener('click', (e) => {
      e.preventDefault();
      const modalId = trigger.getAttribute('data-modal');
      openModal(modalId);
    });
  });

  closeButtons.forEach((btn) => {
    btn.addEventListener('click', (e) => {
      const modal = btn.closest('.modal');
      closeModal(modal);
    });
  });

  // Close modal when pressing Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      modals.forEach((modal) => {
        if (modal.classList.contains('active')) {
          closeModal(modal);
        }
      });
    }
  });
});
