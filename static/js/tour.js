/* AgriSetu — Interactive product tour (Driver.js) */

const TOUR_STORAGE_KEY = "agrisetu_tour_done_v1";

function tourT(key, fallback = "") {
  return window.t ? window.t(key) : fallback;
}

function tourPopoverHtml(title, body) {
  const encoded = encodeURIComponent(`${title}. ${body}`);
  const listenLabel = tourT("tour.listen_step", "Listen to this step");
  return `
    <p class="tour-body">${body}</p>
    <button type="button" class="btn-tts tour-step-tts" data-tts-text="${encoded}" title="${listenLabel}" aria-label="${listenLabel}">
      🔊 ${tourT("tour.listen", "Listen")}
    </button>`;
}

function buildTourSteps() {
  return [
    {
      element: "#field-id",
      popover: {
        title: tourT("tour.field_title", "Select your field"),
        description: tourPopoverHtml(
          tourT("tour.field_title", "Select your field"),
          tourT("tour.field_body", "Choose the field paired with your ESP8266 device.")
        ),
        side: "bottom",
        align: "start",
      },
    },
    {
      element: "#connection-banner",
      popover: {
        title: tourT("tour.connection_title", "Device connection"),
        description: tourPopoverHtml(
          tourT("tour.connection_title", "Device connection"),
          tourT("tour.connection_body", "This banner shows whether your Arduino sensors are online.")
        ),
        side: "bottom",
        align: "center",
      },
    },
    {
      element: "#card-sm",
      popover: {
        title: tourT("tour.sensors_title", "Live sensor readings"),
        description: tourPopoverHtml(
          tourT("tour.sensors_title", "Live sensor readings"),
          tourT("tour.sensors_body", "Soil moisture, temperature, and water level update from your field hardware.")
        ),
        side: "bottom",
        align: "start",
      },
    },
    {
      element: "#advisory-list",
      popover: {
        title: tourT("tour.alerts_title", "Actionable alerts"),
        description: tourPopoverHtml(
          tourT("tour.alerts_title", "Actionable alerts"),
          tourT("tour.alerts_body", "Irrigation, drought, heat, and flood alerts appear here.")
        ),
        side: "top",
        align: "start",
      },
    },
    {
      element: "#irrigation-box",
      popover: {
        title: tourT("tour.irrigation_title", "Smart irrigation"),
        description: tourPopoverHtml(
          tourT("tour.irrigation_title", "Smart irrigation"),
          tourT("tour.irrigation_body", "Get a clear irrigate-now or wait recommendation.")
        ),
        side: "top",
        align: "start",
      },
    },
    {
      element: "#risk-bars",
      popover: {
        title: tourT("tour.risk_title", "Environmental risk"),
        description: tourPopoverHtml(
          tourT("tour.risk_title", "Environmental risk"),
          tourT("tour.risk_body", "Track drought, flood, heat, and disease-climate yield risk scores.")
        ),
        side: "left",
        align: "start",
      },
    },
    {
      element: "#btn-vision",
      popover: {
        title: tourT("tour.vision_title", "Crop health scan"),
        description: tourPopoverHtml(
          tourT("tour.vision_title", "Crop health scan"),
          tourT("tour.vision_body", "Upload a leaf photo or run a demo to detect disease, pest, and nutrient issues.")
        ),
        side: "top",
        align: "start",
      },
    },
    {
      element: "#btn-predict",
      popover: {
        title: tourT("tour.predict_title", "Crop prediction"),
        description: tourPopoverHtml(
          tourT("tour.predict_title", "Crop prediction"),
          tourT("tour.predict_body", "When sensors are online, predict the best crop from live conditions.")
        ),
        side: "top",
        align: "start",
      },
    },
    {
      element: "#analyticsChart",
      popover: {
        title: tourT("tour.analytics_title", "Farm analytics"),
        description: tourPopoverHtml(
          tourT("tour.analytics_title", "Farm analytics"),
          tourT("tour.analytics_body", "Review moisture and yield-risk trends over time.")
        ),
        side: "top",
        align: "center",
      },
    },
  ];
}

function markTourComplete() {
  try {
    localStorage.setItem(TOUR_STORAGE_KEY, "1");
  } catch {
    /* ignore storage errors */
  }
}

function shouldStartTour() {
  try {
    if (localStorage.getItem(TOUR_STORAGE_KEY)) return false;
  } catch {
    /* allow tour if storage unavailable */
  }
  return Boolean(window.AGRISETU_FRESH_LOGIN);
}

function startProductTour() {
  if (!window.driver?.js?.driver) {
    console.warn("Driver.js not loaded — tour skipped.");
    return;
  }

  const driverObj = window.driver.js.driver({
    showProgress: true,
    animate: true,
    overlayColor: "rgba(0,0,0,.72)",
    stagePadding: 8,
    stageRadius: 8,
    popoverClass: "agrisetu-tour-popover",
    nextBtnText: tourT("tour.next", "Next →"),
    prevBtnText: tourT("tour.prev", "← Back"),
    doneBtnText: tourT("tour.done", "Finish tour"),
    steps: buildTourSteps(),
    onDestroyed: markTourComplete,
  });

  driverObj.drive();
}

function maybeStartProductTour() {
  if (!shouldStartTour()) return;
  setTimeout(startProductTour, 900);
}

window.startProductTour = startProductTour;
window.maybeStartProductTour = maybeStartProductTour;
