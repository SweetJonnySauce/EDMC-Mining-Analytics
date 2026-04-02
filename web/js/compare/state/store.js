export function createCompareStore(initialState) {
  let state = {
    ...(initialState && typeof initialState === "object" ? initialState : {})
  };
  const listeners = new Set();

  const notify = (nextState, previousState) => {
    listeners.forEach((listener) => {
      try {
        listener(nextState, previousState);
      } catch (_error) {
        // Keep store updates resilient to listener errors.
      }
    });
  };

  const patch = (partialState) => {
    if (!partialState || typeof partialState !== "object") {
      return state;
    }
    let changed = false;
    const nextState = { ...state };
    Object.keys(partialState).forEach((key) => {
      if (nextState[key] === partialState[key]) {
        return;
      }
      nextState[key] = partialState[key];
      changed = true;
    });
    if (!changed) {
      return state;
    }
    const previousState = state;
    state = nextState;
    notify(state, previousState);
    return state;
  };

  const subscribe = (listener) => {
    if (typeof listener !== "function") {
      return () => {};
    }
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  };

  return {
    getState: () => state,
    patch,
    subscribe
  };
}
