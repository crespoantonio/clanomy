// Clanomy Landing Page Interactive Script (Vanilla JS)

document.addEventListener('DOMContentLoaded', () => {
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

  let isAnnual = false;

  function updatePricing(annual) {
    isAnnual = annual;
    if (billingToggle) {
      billingToggle.classList.toggle('annual', isAnnual);
    }
    if (monthlyLabel && annualLabel) {
      monthlyLabel.classList.toggle('active', !isAnnual);
      annualLabel.classList.toggle('active', isAnnual);
    }

    if (soloPrice && soloPeriod) {
      soloPrice.textContent = isAnnual ? '49.99' : '4.99';
      soloPeriod.textContent = isAnnual ? '/ year' : '/ month';
    }
    if (duoPrice && duoPeriod) {
      duoPrice.textContent = isAnnual ? '79.99' : '7.99';
      duoPeriod.textContent = isAnnual ? '/ year' : '/ month';
    }
    if (familyPrice && familyPeriod) {
      familyPrice.textContent = isAnnual ? '119.99' : '11.99';
      familyPeriod.textContent = isAnnual ? '/ year' : '/ month';
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

  // 2. FAQ Accordion
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

  // 3. Legal Modals (Terms, Privacy, Refund)
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
