import { useEffect, useRef } from "react";
import { useAuth } from "@/context/AuthContext";
import { useBrand } from "@/context/BrandContext";

/**
 * Cross-context invariant connector.
 *
 * Contract: ``tab_selected_brand`` is a per-browser workspace preference
 * that must NOT survive an authenticated → unauthenticated transition.
 * Without this, the next user signing in on the same browser inherits
 * the previous user's selected brand and lands in the wrong workspace
 * before the brand-selection page can re-derive it from server scope.
 *
 * Why this lives here, not inside ``AuthContext`` or ``BrandContext``:
 *   - ``AuthContext`` already owns the logout server contract;
 *     ``BrandContext`` already owns the brand persistence contract.
 *     Adding a cross-domain import there re-introduces coupling the two
 *     contexts were designed to avoid.
 *   - The invariant is "when auth becomes unauthenticated, brand must
 *     clear". That is a *transition rule*, which belongs to a consumer
 *     that observes both states.
 *
 * Authoritative: ANY code path that drives ``AuthContext.user`` from
 * truthy to ``false`` triggers this — including future logout entry
 * points that don't go through ``AppShell.doLogout``. We watch the
 * actual auth state, not a particular logout call site, so the fix
 * isn't pinned to a single button.
 */
export default function BrandAuthSync() {
  const { user } = useAuth();
  const { clearSelectedBrand } = useBrand();
  const prevUserRef = useRef(user);

  useEffect(() => {
    const wasAuthenticated = Boolean(prevUserRef.current);
    const isAuthenticated = Boolean(user);

    // Only clear on the truthy → false edge; mere guest rendering on
    // first load (both prev and current = null/false) is a no-op.
    if (wasAuthenticated && !isAuthenticated) {
      clearSelectedBrand();
    }

    prevUserRef.current = user;
  }, [user, clearSelectedBrand]);

  return null;
}
