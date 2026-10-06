# 在共享原生会话中派发性能显示请求，不启动背包或战报采集。
from src.integrations.nte_core_protocol import NteCoreRpcError


def configure_performance(session, payload):
    enabled = payload["enabled"]
    if enabled:
        session._guard("native_load")
    # The session lock serializes this short control RPC with account close/replacement.
    with session._lock:
        client = session._connect() if enabled else session._client
        if client is None or not client.is_running:
            if enabled:
                raise LookupError("等待原生组件")
            return {"enabled": False, "overlay": False, "installed": False, "rejected": False}
        if "native_performance_v1" not in (client.hello_result or {}).get("capabilities", ()):
            raise NotImplementedError("当前组件不支持性能悬浮窗，需要配套更新")
        result = client.call("native.performance.configure", payload, timeout=2.0)
        if (not isinstance(result, dict)
                or any(type(result.get(k)) is not bool for k in ("enabled", "overlay", "installed", "rendered", "rejected"))
                or result["enabled"] != enabled or result["overlay"] != payload["overlay"]
                or result.get("cost_coverage") != "native_dispatch_and_hud_v1"
                or result.get("cost_complete") is not False
                or (result.get("cost_us") is not None and
                    (type(result["cost_us"]) is not int or result["cost_us"] < 0))):
            raise ValueError("性能组件返回的状态未确认")
        session._performance_active = enabled
        return result


def read_performance_status(self):
    """Read counters on an existing connection; never start capture or connect."""
    self._guard("native_sync")
    with self._lock:
        client, context = self._client, self._current_context()
        if (client is None or self._failed or self._close_requested.is_set()
                or not self._context_matches() or not client.is_running):
            raise LookupError("native_session_unavailable")
    status = self._status_queries.read(client, timeout=2.0)
    self._guard("native_sync")
    if (client is not self._client or context != self._current_context()
            or self._close_requested.is_set()):
        raise LookupError("native_session_changed")
    return client, status


def control_performance_trace(session, payload, context_key):
    if payload['action'] != 'stop':
        session._guard('native_load')
    with session._lock:
        if session._current_context() != context_key or session._close_requested.is_set():
            raise LookupError('账号或会话已改变，未向新会话发送采样指令')
        client = session._connect() if payload['action'] == 'start' else session._client
        if client is None or not client.is_running:
            raise LookupError('原生会话已断开')
        if 'native_performance_trace_v1' not in (client.hello_result or {}).get('capabilities', ()):
            raise NotImplementedError('当前组件不支持细分性能采样，需要更新配套 Core、宿主和插件')
        if session._current_context() != context_key:
            raise LookupError('账号已改变')
        if payload['action'] == 'start':
            session._performance_trace_active = True  # An unknown result must retain the lease.
            session._performance_trace_owner = (client, payload['trace_id'])
        elif session._performance_trace_owner != (client, payload['trace_id']):
            raise LookupError('采样所属连接已改变，未向新连接发送旧采样指令')
        try:
            result = client.call('native.performance.trace', payload, timeout=2.0)
        except NteCoreRpcError as error:
            if payload['action'] == 'start' and error.message in {
                'performance_plugin_unavailable', 'performance_busy', 'performance_start_failed',
                'invalid_trace_id', 'invalid_action', 'invalid_services',
            }:
                session._performance_trace_active = False
            raise
        if isinstance(result, dict) and result.get('trace_id') == payload['trace_id'] and result.get('active') is False:
            session._performance_trace_active = False
        return result
