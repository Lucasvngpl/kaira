// The first thing any device sees: who is holding it? The clinician runs
// the assessment; the patient device only ever shows stimuli. Choosing
// stamps the role into the URL so a refresh (or an iPad bookmark of
// ?role=patient) never asks again.
import { FiMonitor, FiUser } from 'react-icons/fi';
import '../styles/session.css';

export default function RoleScreen({ onChoose }) {
  const choose = (role) => {
    const url = new URL(window.location.href);
    url.searchParams.set('role', role);
    window.history.replaceState(null, '', url);
    onChoose(role);
  };

  return (
    <div className="sn-role kr-reveal">
      <h1 className="sn-role__title">Who is using this device?</h1>
      <div className="sn-role__choices">
        <button className="sn-role__choice" onClick={() => choose('clinician')}>
          <FiMonitor aria-hidden="true" />
          <span>Clinician</span>
          <small>Run the assessment: baseline, tasks, scoring, report.</small>
        </button>
        <button className="sn-role__choice" onClick={() => choose('patient')}>
          <FiUser aria-hidden="true" />
          <span>Patient screen</span>
          <small>Shows only the test drawings. Put this on the patient's display.</small>
        </button>
      </div>
    </div>
  );
}
