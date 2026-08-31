// Hand-made sample report behind ?demo=report - lets anyone deep-link into
// the report screen without running a session. PT-SAMPLE on purpose: any
// screenshot of this data identifies itself as fabricated.
// Internally consistent with decide.py's table: climb, a double no-effort
// miss (second one flagged disengaged), an ease, then three high-effort
// holds that converge at level 3.
export const SAMPLE_REPORT = {
  domain: 'Memory',
  patient_ref: 'PT-SAMPLE',
  date: '2026-09-13',
  final_level: 3,
  level_max: 5,
  reason: 'Three consecutive correct at one level',
  end_reason: 'converged',
  converged: true,
  band: [0.67, 1.5],
  baseline_sd: 0.21,
  mean_rt: 9.8,
  accuracy: 0.63,
  disengaged_count: 1,
  untrusted_rate: 0.0,
  tasks: [
    { n: 1, task_id: 'mem_l2_001', kind: 'word_list', level: 2, result: 'correct', load: 0.72, z: -1.57, bars: 2, trusted: true, rt: 5.1, action: 'up', reason: 'up', reason_text: 'Correct at mid effort - stepping up to level 3.', quadrant: 'efficient', flag: false },
    { n: 2, task_id: 'mem_l3_001', kind: 'word_list', level: 3, result: 'correct', load: 1.41, z: 1.64, bars: 4, trusted: true, rt: 8.3, action: 'up', reason: 'up', reason_text: 'Correct at mid effort - stepping up to level 4.', quadrant: 'efficient', flag: false },
    { n: 3, task_id: 'mem_l4_001', kind: 'word_list', level: 4, result: 'incorrect', load: 0.64, z: -2.12, bars: 1, trusted: true, rt: 11.2, action: 'repeat', reason: 'repeat', reason_text: 'Wrong at low effort - repeating level 4 with a new item.', quadrant: 'disengaged', flag: false },
    { n: 4, task_id: 'mem_l4_002', kind: 'word_list', level: 4, result: 'incorrect', load: 0.61, z: -2.35, bars: 1, trusted: true, rt: 9.8, action: 'repeat', reason: 'repeat', reason_text: 'Wrong at low effort - repeating level 4 with a new item.', quadrant: 'disengaged', flag: true },
    { n: 5, task_id: 'mem_l4_003', kind: 'digit_span', level: 4, result: 'incorrect', load: 2.35, z: 4.07, bars: 5, trusted: true, rt: 16.9, action: 'down', reason: 'down', reason_text: 'Wrong at high effort - easing to level 3.', quadrant: 'struggling', flag: false },
    { n: 6, task_id: 'mem_l3_002', kind: 'word_list', level: 3, result: 'correct', load: 1.62, z: 2.3, bars: 5, trusted: true, rt: 9.1, action: 'hold', reason: 'hold', reason_text: 'Correct at high effort - holding at level 3.', quadrant: 'effortful', flag: false },
    { n: 7, task_id: 'mem_l3_003', kind: 'digit_span', level: 3, result: 'correct', load: 1.55, z: 2.09, bars: 5, trusted: true, rt: 8.7, action: 'hold', reason: 'hold', reason_text: 'Correct at high effort - holding at level 3.', quadrant: 'effortful', flag: false },
    { n: 8, task_id: 'mem_l3_004', kind: 'digit_span_backward', level: 3, result: 'correct', load: 1.58, z: 2.18, bars: 5, trusted: true, rt: 9.6, action: 'hold', reason: 'hold', reason_text: 'Correct at high effort - holding at level 3.', quadrant: 'effortful', flag: false },
  ],
};
