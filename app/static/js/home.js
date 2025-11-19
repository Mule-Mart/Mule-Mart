document.addEventListener("DOMContentLoaded", function() {
  const urlParams = new URLSearchParams(window.location.search);

  // Auto-scroll to results when searching
  if (urlParams.get("search")) {
    const resultsSection = document.querySelector("#search-results");
    if (resultsSection) {
      resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  // Auto-reset search when cleared
  const input = document.getElementById("search-input");
  const form = document.getElementById("search-form");

  if (input && form) {
    input.addEventListener("input", function() {
      if (this.value === "") {
        window.location.href = form.getAttribute("action");
      }
    });
  }
});

document.querySelector("form").addEventListener("submit", function (e) {
  const price = document.getElementById("price_offer").value;
  if (price <= 0) {
      alert("Please enter a valid price.");
      e.preventDefault();
  }
});


function confirmDelivery(orderId) {
  fetch(`/confirm_order/${orderId}`, {
      method: "POST",
      headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": "{{ csrf_token() }}"
      }
  })
  .then(response => {
      if(response.ok) {
          location.reload();
      }
  })
  .catch(err => console.error(err));
}

