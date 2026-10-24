document.addEventListener('DOMContentLoaded', () => {
  const pickup = document.querySelector('input[name="pickup_date"]');
  const ret = document.querySelector('input[name="return_date"]');
  const pickupTime = document.querySelector('input[name="pickup_time"]');
  const returnTime = document.querySelector('input[name="return_time"]');
  const total = document.getElementById('estimated-total');
  const price = Number(window.DRIVEEASE_PRICE || 0);
  const today = new Date();
  const localToday = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;
  if (pickup && ret) {
    pickup.min = pickup.min || localToday;
    ret.min = pickup.value || ret.min || localToday;
    const syncDates = () => {
      ret.min = pickup.value || localToday;
      if (ret.value && pickup.value && ret.value < pickup.value) ret.value = pickup.value;
      updateEstimate();
    };
    pickup.addEventListener('change', syncDates);
    ret.addEventListener('change', updateEstimate);
    pickup.addEventListener('change', () => { if (pickup.value === ret.value && pickupTime && returnTime && returnTime.value <= pickupTime.value) returnTime.value = pickupTime.value; });
  }
  [pickupTime, returnTime].forEach(el => el && el.addEventListener('change', updateEstimate));
  function updateEstimate() {
    if (!total || !pickup || !ret || !pickup.value || !ret.value) return;
    const start = new Date(`${pickup.value}T${pickupTime?.value || '10:00'}:00`);
    const end = new Date(`${ret.value}T${returnTime?.value || '10:00'}:00`);
    if (end <= start) { total.textContent = 'Check return date/time'; return; }
    const dayDiff = Math.max(1, Math.round((new Date(`${ret.value}T00:00:00`) - new Date(`${pickup.value}T00:00:00`)) / 86400000));
    total.textContent = new Intl.NumberFormat('en-IN', {style:'currency', currency:'INR', maximumFractionDigits:2}).format(dayDiff * price);
  }
  updateEstimate();
  document.querySelectorAll('.flash').forEach(message => {
    window.setTimeout(() => { message.style.transition = 'opacity .4s'; message.style.opacity = '0'; window.setTimeout(() => message.remove(), 450); }, 6000);
  });
  document.querySelectorAll('form').forEach(form => {
    form.addEventListener('submit', event => {
      if (form.id !== 'booking-form') return;
      const startDate = form.querySelector('[name="pickup_date"]')?.value;
      const endDate = form.querySelector('[name="return_date"]')?.value;
      const startTime = form.querySelector('[name="pickup_time"]')?.value || '00:00';
      const endTime = form.querySelector('[name="return_time"]')?.value || '00:00';
      if (startDate && endDate && `${endDate}T${endTime}` <= `${startDate}T${startTime}`) {
        event.preventDefault();
        alert('Return date and time must be after pickup date and time.');
      }
    });
  });
});