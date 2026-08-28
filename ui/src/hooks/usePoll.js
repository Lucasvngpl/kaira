// House polling pattern: setInterval inside an effect, gated on a derived
// boolean, cleanup on unmount or gate flip. The callback is held in a ref so
// callers can pass an inline arrow without the identity change re-arming the
// interval every render (same trick as UQwest's useCachedResource).
import { useEffect, useRef } from 'react';

export default function usePoll(fn, ms, active) {
  const fnRef = useRef(fn);
  fnRef.current = fn;

  useEffect(() => {
    if (!active) return undefined;
    fnRef.current(); // fire immediately - a 1s blank readout is a visible stall
    const id = setInterval(() => fnRef.current(), ms);
    return () => clearInterval(id);
  }, [ms, active]);
}
