// Draft owners register a save boundary. Navigation proceeds only after the
// latest draft is saved; failed saves keep the patient on the current screen.
let activeGuard = null;
let navigationSequence = 0;

export function registerNavigationGuard(guard) {
  activeGuard = guard;
  return () => {
    if (activeGuard === guard) activeGuard = null;
  };
}

export async function navigateWithGuard(action) {
  const sequence = ++navigationSequence;
  const guard = activeGuard;
  if (guard && !(await guard())) return false;
  if (sequence !== navigationSequence) return false;
  await action();
  return true;
}
