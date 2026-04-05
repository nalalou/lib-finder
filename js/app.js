(function () {
  "use strict";

  function validateZipcode(zip) {
    if (!zip || zip.length !== 5) return "Please enter a 5-digit zipcode.";
    if (!/^\d{5}$/.test(zip)) return "Zipcode must be 5 digits.";
    return null;
  }

  function getPrefix(zip) {
    return zip.slice(0, 3);
  }

  function findLibraries(data, zip) {
    if (!data || !data.libraries) return [];
    return data.libraries.filter(function (lib) {
      return lib.zipcodes.includes(zip);
    });
  }

  function getLibraryUrl(library) {
    return library.formUrl || library.website;
  }

  function needsSubmitPrompt(library) {
    return library.formStatus === "unknown";
  }

  var zipcodeInput = document.getElementById("zipcode-input");
  var findBtn = document.getElementById("find-btn");
  var errorMsg = document.getElementById("error-msg");
  var multiPicker = document.getElementById("multi-picker");
  var libraryList = document.getElementById("library-list");
  var submitPrompt = document.getElementById("submit-prompt");
  var showSubmitFormBtn = document.getElementById("show-submit-form");
  var submitFormContainer = document.getElementById("submit-form-container");
  var submitContext = document.getElementById("submit-context");
  var submitUrl = document.getElementById("submit-url");
  var honeypot = document.getElementById("honeypot");
  var submitBtn = document.getElementById("submit-btn");
  var submitStatus = document.getElementById("submit-status");

  var currentLibraries = [];
  var currentZipcode = "";

  function showError(msg) {
    errorMsg.textContent = msg;
    errorMsg.hidden = false;
  }

  function clearError() {
    errorMsg.textContent = "";
    errorMsg.hidden = true;
  }

  function resetUI() {
    clearError();
    multiPicker.hidden = true;
    submitPrompt.hidden = true;
    submitFormContainer.hidden = true;
    submitStatus.textContent = "";
    submitStatus.className = "submit-status";
    libraryList.innerHTML = "";
    currentLibraries = [];
  }

  function openLibrary(library) {
    var url = getLibraryUrl(library);
    window.open(url, "_blank", "noopener");

    if (needsSubmitPrompt(library)) {
      submitContext.textContent = "Submitting for: " + library.name;
      submitPrompt.hidden = false;
    }
  }

  function renderPicker(libraries) {
    libraryList.innerHTML = "";
    libraries.forEach(function (lib) {
      var li = document.createElement("li");
      var a = document.createElement("a");
      a.href = getLibraryUrl(lib);
      a.target = "_blank";
      a.rel = "noopener";
      a.innerHTML =
        '<span class="lib-name">' + lib.name + "</span><br>" +
        '<span class="lib-address">' + lib.address + "</span>";
      a.addEventListener("click", function (e) {
        e.preventDefault();
        openLibrary(lib);
      });
      li.appendChild(a);
      libraryList.appendChild(li);
    });
    multiPicker.hidden = false;
  }

  async function lookup(zip) {
    resetUI();
    currentZipcode = zip;

    var validationError = validateZipcode(zip);
    if (validationError) {
      showError(validationError);
      return;
    }

    var prefix = getPrefix(zip);

    try {
      var response = await fetch("/data/libraries-" + prefix + ".json");
      if (!response.ok) {
        showError("No libraries found for this zipcode.");
        return;
      }
      var data = await response.json();
      var libraries = findLibraries(data, zip);

      if (libraries.length === 0) {
        showError("No libraries found for this zipcode.");
        return;
      }

      currentLibraries = libraries;

      if (libraries.length === 1) {
        openLibrary(libraries[0]);
      } else {
        renderPicker(libraries);
      }
    } catch (e) {
      showError("Something went wrong. Please try again.");
    }
  }

  async function submitForm() {
    var url = submitUrl.value.trim();

    if (!url) {
      submitStatus.textContent = "Please paste a URL.";
      submitStatus.className = "submit-status error";
      return;
    }

    if (honeypot.value) return;

    submitBtn.disabled = true;
    submitStatus.textContent = "Submitting...";
    submitStatus.className = "submit-status";

    try {
      var response = await fetch("/api/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          zipcode: currentZipcode,
          libraryName: currentLibraries.length > 0 ? currentLibraries[0].name : "Unknown",
          formUrl: url,
        }),
      });

      if (response.ok) {
        submitStatus.textContent = "Thanks! We'll review and add this link.";
        submitStatus.className = "submit-status success";
        submitUrl.value = "";
      } else {
        var data = await response.json().catch(function () { return {}; });
        submitStatus.textContent = data.error || "Submission failed. Please try again.";
        submitStatus.className = "submit-status error";
      }
    } catch (e) {
      submitStatus.textContent = "Submission failed. Please try again.";
      submitStatus.className = "submit-status error";
    } finally {
      submitBtn.disabled = false;
    }
  }

  findBtn.addEventListener("click", function () {
    lookup(zipcodeInput.value.trim());
  });

  zipcodeInput.addEventListener("keydown", function (e) {
    if (e.key === "Enter") {
      lookup(zipcodeInput.value.trim());
    }
  });

  zipcodeInput.addEventListener("input", function () {
    zipcodeInput.value = zipcodeInput.value.replace(/\D/g, "").slice(0, 5);
  });

  showSubmitFormBtn.addEventListener("click", function () {
    submitFormContainer.hidden = false;
    submitUrl.focus();
  });

  submitBtn.addEventListener("click", submitForm);

  submitUrl.addEventListener("keydown", function (e) {
    if (e.key === "Enter") submitForm();
  });
})();
