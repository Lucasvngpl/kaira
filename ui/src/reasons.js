// decide.py's machine reasons -> clinician-facing copy, in ONE dictionary so
// the vocabulary grows here and nowhere else. Unknown strings fall through
// raw on purpose: a new reason should be seen and added, not silently hidden.
export const REASON_COPY = {
  // The real vocabulary (decide.py docstring). This copy starts appearing
  // the moment the team's algorithm lands; nothing else changes.
  correct_easy: 'Correct with effort below range',
  correct_engaged: 'Correct, effort in range',
  incorrect_engaged: 'Incorrect while working hard',
  incorrect_disengaged: 'Incorrect with no effort behind it',
  // Placeholder decide (ignores the EEG); these disappear with the real file.
  placeholder_correct: 'Correct (EEG rule pending)',
  placeholder_not_correct: 'Not correct (EEG rule pending)',
};

export const reasonCopy = (reason) => REASON_COPY[reason] || reason;
