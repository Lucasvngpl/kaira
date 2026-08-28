// Hand-made sample report behind ?demo=report - lets anyone deep-link into
// the report screen (and its expand animation) without running a session.
// PT-SAMPLE on purpose: any screenshot of this data identifies itself as
// fabricated. It is not derived from any recording.
// Internally consistent: accuracy 7/9, one flagged trial, convergence on the
// last three corrects at level 3 inside the band.
export const SAMPLE_REPORT = {
  domain: 'Memory',
  patient_ref: 'PT-SAMPLE',
  date: '2026-09-13',
  final_level: 3,
  level_max: 5,
  reason: 'Three consecutive correct at stable load',
  converged: true,
  band: [0.8, 3.0],
  mean_rt: 9.0,
  accuracy: 0.78,
  disengaged_count: 1,
  tasks: [
    { n: 1, task_id: 'mem_l2_001', level: 2, result: 'correct', load: 0.72, trusted: true, rt: 5.1, action: 'advance', reason: 'correct_easy', flag: false },
    { n: 2, task_id: 'mem_l3_001', level: 3, result: 'correct', load: 1.41, trusted: true, rt: 8.3, action: 'hold', reason: 'correct_engaged', flag: false },
    { n: 3, task_id: 'mem_l3_002', level: 3, result: 'incorrect', load: 0.64, trusted: true, rt: 11.2, action: 'flag', reason: 'incorrect_disengaged', flag: true },
    { n: 4, task_id: 'mem_l3_003', level: 3, result: 'incorrect', load: 2.35, trusted: true, rt: 16.9, action: 'ease', reason: 'incorrect_engaged', flag: false },
    { n: 5, task_id: 'mem_l2_002', level: 2, result: 'correct', load: 1.18, trusted: true, rt: 7.4, action: 'hold', reason: 'correct_engaged', flag: false },
    { n: 6, task_id: 'mem_l2_003', level: 2, result: 'correct', load: 0.69, trusted: true, rt: 4.8, action: 'advance', reason: 'correct_easy', flag: false },
    { n: 7, task_id: 'mem_l3_004', level: 3, result: 'correct', load: 1.52, trusted: true, rt: 9.1, action: 'hold', reason: 'correct_engaged', flag: false },
    { n: 8, task_id: 'mem_l3_005', level: 3, result: 'correct', load: 1.66, trusted: true, rt: 8.7, action: 'hold', reason: 'correct_engaged', flag: false },
    { n: 9, task_id: 'mem_l3_001', level: 3, result: 'correct', load: 1.38, trusted: true, rt: 9.6, action: 'hold', reason: 'correct_engaged', flag: false },
  ],
};
