"""One conservative policy for health and queue fallback; never execution proof."""
from datetime import datetime
import math


def _timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.timestamp() if parsed.tzinfo is not None and parsed.utcoffset().total_seconds() == 0 else None
    except (TypeError, ValueError, AttributeError, OverflowError):
        return None


def observe_availability(previous, capabilities, profile_id, now, monotonic_now=None):
    """Pure durable observation reducer. Equal revisions never renew local TTL."""
    monotonic_now = now if monotonic_now is None else monotonic_now
    epoch = now - monotonic_now
    previous = dict(previous or {})
    descriptor = capabilities.get("routing_availability_v1", {})
    if not isinstance(descriptor, dict):
        return previous, False
    revision = descriptor.get("revision")
    if (descriptor.get("schema_version") != "1" or type(revision) is not int or revision < 0
            or not isinstance(descriptor.get("profiles"), list)
            or not 1 <= len(descriptor["profiles"]) <= 64):
        return previous, False
    profile_ids = [p.get("profile_id") if isinstance(p, dict) else None for p in descriptor["profiles"]]
    if any(not isinstance(p, str) or not p or len(p) > 128 for p in profile_ids) or len(set(profile_ids)) != len(profile_ids):
        return previous, False
    profile = next((p for p in descriptor["profiles"] if isinstance(p, dict)
                    and p.get("profile_id") == profile_id and p.get("profile_revision") == "1"), None)
    if (not profile or profile.get("health") not in {"available", "unavailable", "unknown"}
            or profile.get("capacity") not in {"idle", "busy"}
            or profile.get("reason_code") not in {"ready", "tool_missing", "version_unsupported", "auth_unavailable",
                "quota_exhausted", "resource_unavailable", "probe_failed", "unverified", "stale"}
            or profile.get("evidence_kind") not in {"local_probe", "provider_error", "operator_validation",
                                                   "operator_attested_preflight", "account_status", "none"}):
        return previous, False
    if "observed_at" not in profile or "valid_until" not in profile:
        return previous, False
    observed, until = _timestamp(profile["observed_at"]), _timestamp(profile["valid_until"])
    if profile["observed_at"] is not None or profile["valid_until"] is not None:
        if observed is None or until is None or not 0 < until - observed <= 90:
            return previous, False
    if revision < previous.get("revision", -1):
        return previous, True
    # The descriptor revision is global, not a per-profile heartbeat. Another
    # profile's report cannot renew this profile's TTL or recovery evidence.
    if previous and (abs(epoch - previous.get("clock_epoch", epoch)) >= 5
                     or not 0 <= monotonic_now - previous.get("received_monotonic", -math.inf) < 90
                     or (previous.get("valid_until") or 0) <= now):
        previous.update(health="unknown", impaired=True, healthy_since=None, healthy_since_monotonic=None, healthy_reports=0)
    if revision == previous.get("revision"):
        return previous, True
    if previous and observed is not None and observed <= (previous.get("profile_observed_at") or -math.inf):
        previous["revision"] = revision
        if profile["health"] != "available":
            previous.update(health=profile["health"], impaired=True, healthy_since=None, healthy_since_monotonic=None, healthy_reports=0)
        return previous, True
    fresh = observed is not None and until is not None and observed <= now + 5 and observed <= until and until > now
    health = profile["health"] if fresh else "unknown"
    impaired = previous.get("impaired", False) or health != "available"
    since = previous.get("healthy_since") if previous.get("health") == "available" else None
    since_monotonic = previous.get("healthy_since_monotonic") if since is not None else None
    count = previous.get("healthy_reports", 0) if since is not None else 0
    if health == "available":
        since = now if since is None else since
        since_monotonic = monotonic_now if since_monotonic is None else since_monotonic
        count += 1
        if count >= 2 and monotonic_now - since_monotonic >= 60:
            impaired = False
    else:
        since, since_monotonic, count = None, None, 0
    return {"revision": revision, "received_at": now, "valid_until": until,
            "profile_observed_at": observed, "received_monotonic": monotonic_now, "clock_epoch": epoch,
            "health": health, "capacity": profile["capacity"], "impaired": impaired,
            "healthy_since": since, "healthy_since_monotonic": since_monotonic, "healthy_reports": count}, True


def routing_decision(*, observation, capabilities, enabled, local_only, submitted,
                     queue_elapsed, queue_wait_seconds, now, monotonic_now=None):
    """Return bridge/cloud/withdraw/wait; cloud still requires native admission."""
    if not enabled or local_only:
        return "bridge", "bridge_only"
    if not observation:
        return "bridge", "availability_contract_unavailable"
    admission = capabilities.get("admission", {})
    node = capabilities.get("node_status", {})
    if admission.get("accepting_new_tasks") is not True or admission.get("mode") != "enabled":
        return "wait", "bridge_administrator_paused"
    if node.get("authorization") != "active":
        return "wait", "bridge_node_not_authorized"
    monotonic_now = now if monotonic_now is None else monotonic_now
    fresh = (abs(now - monotonic_now - observation.get("clock_epoch", now - monotonic_now)) < 5
             and 0 <= monotonic_now - observation.get("received_monotonic", -math.inf) < 90
             and (observation.get("valid_until") or 0) > now)
    unavailable = not fresh or observation.get("health") != "available" or observation.get("impaired")
    queue_expired = queue_elapsed is not None and queue_elapsed >= queue_wait_seconds
    if unavailable or queue_expired:
        return ("withdraw" if submitted else "cloud"), ("local_unavailable" if unavailable else "queue_wait_exceeded")
    return "bridge", "local_available"
