// Tutorial step controller

const steps = [];
let currentStep = 0;

function nextStep() {
  if (currentStep < steps.length - 1) {
    currentStep++;
    renderStep(currentStep);
  }
}

function renderStep(index) {
  // TODO: display tutorial step content
}
