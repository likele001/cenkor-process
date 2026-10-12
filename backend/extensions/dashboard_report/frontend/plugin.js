/*
 * 经营驾驶舱与数据大屏（dashboard_report）前端插件 —— 跨域 KPI 驾驶舱 / 趋势 / 告警 / 目标设置 / 大屏模式
 * 协议：window.__registerExtension({ key, menus, routes, locales })
 * 原生 Vue.h + 内联渲染；后端前缀 /api/extensions/dashboard_report
 */
;(function () {
  var Vue = window.Vue
  if (!Vue || !window.__registerExtension) { console.warn('[dashboard_report] 宿主未提供注册桥，跳过注册'); return }
  var h = Vue.h, ref = Vue.ref, reactive = Vue.reactive, onMounted = Vue.onMounted, onUnmounted = Vue.onUnmounted, watch = Vue.watch
  var API = '/extensions/dashboard_report', PREFIX = '/api'
  var HOST = window.__cenkorHost

  function token() { return sessionStorage.getItem('cenkormes_admin_token') || localStorage.getItem('cenkormes_admin_token') || '' }
  async function req(method, path, body, params) {
    if (HOST && typeof HOST.request === 'function' && method === 'GET') { return await HOST.request(method, API + path, body, params) }
    var qs = params ? ('?' + new URLSearchParams(params).toString()) : ''
    var heads = { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token() }
    var hasBody = method !== 'GET' && method !== 'DELETE' && body
    var resp = await fetch(PREFIX + API + path + qs, { method: method, headers: heads, body: hasBody ? JSON.stringify(body) : undefined })
    var j = await resp.json().catch(function () { return {} })
    if (j && j.code && j.code !== 200) { throw new Error(j.msg || ('业务错误 ' + j.code)) }
    if (!resp.ok) { throw new Error((j && j.detail) || ('请求失败 ' + resp.status)) }
    return j.data
  }
  var extGet = function (p, q) { return req('GET', p, null, q) }
  var extPost = function (p, b) { return req('POST', p, b || {}) }
  var extDelete = function (p) { return req('DELETE', p) }

  var DOMAIN_ORDER = ['生产', '质量', '物料', '清洗', '库存']
  var STATUS_COLOR = { good: '#16a34a', warn: '#ea580c', bad: '#dc2626', neutral: '#6b7280' }
  var STATUS_BG = { good: '#f0fdf4', warn: '#fff7ed', bad: '#fef2f2', neutral: '#f8fafc' }

  function fmtVal(m) {
    if (m.value === null || m.value === undefined) return '—'
    var v = Number(m.value)
    if (m.fmt === 'pct') return v.toFixed(2).replace(/\.?0+$/, '') + (m.unit || '')
    if (m.fmt === 'int') return Math.round(v).toLocaleString() + (m.unit ? ' ' + m.unit : '')
    // num
    return (v >= 10000 ? (v / 10000).toFixed(2) + '万' : v.toLocaleString(undefined, { maximumFractionDigits: 2 })) + (m.unit ? ' ' + m.unit : '')
  }

  var App = { setup: function () {
    var days = ref(30)
    var metrics = ref([])
    var domains = ref({})
    var trend = ref([])
    var alerts = ref([])
    var err = ref('')
    var big = ref(false)
    var showTargets = ref(false)
    var targetsCfg = ref([])
    var targetRows = ref([])
    var busy = ref('')
    var timer = ref(null)

    async function refresh() {
      err.value = ''
      try {
        var sc = await extGet('/screen', { days: days.value })
        metrics.value = sc.cockpit.metrics; domains.value = sc.cockpit.domains
        trend.value = sc.trend.series; alerts.value = sc.alerts
      } catch (e) { err.value = e.message }
    }
    async function loadTargets() {
      try { var t = await extGet('/targets'); targetRows.value = (t.configured || []).reduce(function (acc, c) { acc[c.metric_key] = { name: c.name || '', better: c.better, target_value: c.target_value || '', warn_value: c.warn_value || '' }; return acc }, {}); targetsCfg.value = t.metrics } catch (e) { err.value = e.message }
    }
    async function saveTarget(key) {
      var r = targetRows.value[key] || {}; busy.value = key; err.value = ''
      try { await extPost('/targets', { metric_key: key, name: r.name, better: r.better, target_value: r.target_value, warn_value: r.warn_value }); await refresh(); alert('已保存：' + key) } catch (e) { err.value = e.message } finally { busy.value = '' }
    }
    async function delTarget(key) {
      try { await extDelete('/targets/' + key); if (targetRows.value[key]) targetRows.value[key] = { name: '', better: '', target_value: '', warn_value: '' }; await refresh() } catch (e) { err.value = e.message }
    }
    function toggleBig() {
      big.value = !big.value
      if (big.value) { if (timer.value) clearInterval(timer.value); timer.value = setInterval(refresh, 30000) }
      else if (timer.value) { clearInterval(timer.value); timer.value = null }
    }
    onMounted(function () { refresh(); loadTargets() })
    onUnmounted(function () { if (timer.value) clearInterval(timer.value) })
    watch(days, refresh)

    // ---- KPI 卡 ----
    function kpiCard(m) {
      var col = STATUS_COLOR[m.status] || STATUS_COLOR.neutral
      return h('div', { style: 'flex:1;min-width:150px;background:' + STATUS_BG[m.status] + ';border:1px solid ' + (m.status === 'neutral' ? '#e5e7eb' : col + '55') + ';border-left:4px solid ' + col + ';border-radius:10px;padding:12px 14px;' }, [
        h('div', { style: 'font-size:12px;color:#6b7280;' }, m.label),
        h('div', { style: 'font-size:22px;font-weight:700;color:' + col + ';margin:4px 0;' }, fmtVal(m)),
        h('div', { style: 'font-size:11px;color:#9ca3af;' }, m.reached_pct != null ? ('达成 ' + m.reached_pct + '% · 目标 ' + (m.target || '—')) : (m.target != null ? '目标 ' + m.target : ' ')),
      ])
    }
    function cockpit() {
      if (!metrics.value.length) return h('div', { style: 'color:#6b7280;padding:20px;' }, busy.value || '加载中…')
      var groups = DOMAIN_ORDER.filter(function (d) { return (domains.value[d] || []).length })
      var byKey = {}; metrics.value.forEach(function (m) { byKey[m.key] = m })
      return h('div', null, groups.map(function (d) {
        return h('div', { style: 'margin-bottom:14px;' }, [
          h('div', { style: 'font-size:13px;font-weight:600;color:#374151;margin:6px 2px;' }, d),
          h('div', { style: 'display:flex;flex-wrap:wrap;gap:10px;' }, (domains.value[d] || []).map(function (k) { return kpiCard(byKey[k]) })),
        ])
      }))
    }

    // ---- 趋势条形 ----
    function trendChart() {
      var s = trend.value || []
      if (!s.length) return h('div', { style: 'background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:16px;margin-bottom:14px;' }, h('div', { style: 'color:#9ca3af;font-size:13px;' }, '暂无完成批次趋势。'))
      var maxb = Math.max.apply(null, s.map(function (r) { return Number(r.batch_cnt) || 0 }).concat([1]))
      var bars = s.slice(-20).map(function (r) {
        var hp = Math.round((Number(r.batch_cnt) || 0) / maxb * 100)
        return h('div', { style: 'flex:1;min-width:26px;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:120px;', title: r.d + ' 完成' + r.batch_cnt + '批 产出' + r.output_qty + ' 收率' + (r.avg_yield || '—') }, [
          h('div', { style: 'font-size:11px;color:#6b7280;' }, String(r.batch_cnt)),
          h('div', { style: 'width:60%;background:#2563eb;border-radius:3px 3px 0 0;height:' + Math.max(hp, 4) + 'px;' }),
          h('div', { style: 'font-size:10px;color:#9ca3af;margin-top:4px;transform:rotate(0);white-space:nowrap;' }, String(r.d).slice(5)),
        ])
      })
      return h('div', { style: 'background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:16px;margin-bottom:14px;' }, [
        h('b', { style: 'font-size:14px;' }, '近 ' + days.value + ' 天完成批次趋势'),
        h('div', { style: 'display:flex;align-items:flex-end;gap:4px;margin-top:12px;' }, bars),
      ])
    }

    // ---- 告警 ----
    function alertsList() {
      var a = alerts.value || []
      if (!a.length) return h('div', { style: 'background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:16px;' }, h('span', { style: 'color:#16a34a;' }, '当前无风险告警。'))
      return h('div', { style: 'background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:16px;' }, [
        h('b', { style: 'font-size:14px;' }, '风险告警（' + a.length + '）'),
        h('div', { style: 'margin-top:8px;max-height:320px;overflow:auto;' }, a.map(function (x) {
          var col = x.level === 'danger' ? '#dc2626' : '#ea580c'
          return h('div', { style: 'display:flex;align-items:center;padding:7px 0;border-bottom:1px solid #f1f5f9;font-size:13px;' }, [
            h('span', { style: 'width:8px;height:8px;border-radius:50%;background:' + col + ';margin-right:8px;' }),
            h('span', { style: 'color:' + col + ';font-weight:600;margin-right:8px;' }, x.type),
            h('span', { style: 'flex:1;color:#374151;' }, x.text),
            h('span', { style: 'color:#9ca3af;font-size:12px;' }, String(x.at || '').slice(0, 16)),
          ])
        })),
      ])
    }

    // ---- 目标设置 ----
    function targetsPanel() {
      if (!showTargets.value) return null
      function num(key, field, ph) {
        var r = targetRows.value[key] || {}
        return h('input', { type: 'number', step: '0.01', placeholder: ph, style: 'width:110px;padding:5px 8px;border:1px solid #d1d5db;border-radius:6px;font-size:13px;', value: r[field] || '', onInput: function (e) { if (!targetRows.value[key]) targetRows.value[key] = { name: '', better: '', target_value: '', warn_value: '' }; targetRows.value[key][field] = e.target.value } })
      }
      var rows = targetsCfg.value.map(function (m) {
        var r = targetRows.value[m.key] || {}
        return h('tr', null, [
          h('td', { style: 'padding:7px 8px;border-bottom:1px solid #f1f5f9;font-size:13px;' }, m.domain + ' / ' + m.label + (m.unit ? '（' + m.unit + '）' : '')),
          h('td', { style: 'padding:7px 8px;' }, [h('select', { style: 'padding:5px;border:1px solid #d1d5db;border-radius:6px;font-size:13px;', value: r.better || m.better, onChange: function (e) { if (!targetRows.value[m.key]) targetRows.value[m.key] = { name: '', better: '', target_value: '', warn_value: '' }; targetRows.value[m.key].better = e.target.value } }, [h('option', { value: 'up', selected: (r.better || m.better) === 'up' }, '越大越好'), h('option', { value: 'down', selected: (r.better || m.better) === 'down' }, '越小越好')])]),
          h('td', { style: 'padding:7px 8px;' }, [num(m.key, 'target_value', '目标')]),
          h('td', { style: 'padding:7px 8px;' }, [num(m.key, 'warn_value', '警戒')]),
          h('td', { style: 'padding:7px 8px;' }, [
            h('button', { style: 'padding:5px 10px;border-radius:6px;border:1px solid #2563eb;background:#2563eb;color:#fff;cursor:pointer;font-size:12px;margin-right:6px;', onClick: function () { saveTarget(m.key) } }, busy.value === m.key ? '…' : '保存'),
            h('button', { style: 'padding:5px 10px;border-radius:6px;border:1px solid #fecaca;background:#fef2f2;color:#dc2626;cursor:pointer;font-size:12px;', onClick: function () { delTarget(m.key) } }, '清除'),
          ]),
        ])
      })
      return h('div', { style: 'background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:16px;margin-bottom:14px;' }, [
        h('b', null, 'KPI 目标与警戒阈值'), h('div', { style: 'color:#9ca3af;font-size:12px;margin:6px 0;' }, '达成线（目标）与警戒线（红线）用于驾驶舱红绿灯判定；越优方向决定“越大/越小越好”。'),
        h('table', { style: 'width:100%;border-collapse:collapse;' }, [h('tr', null, ['指标', '方向', '目标值', '警戒值', '操作'].map(function (t) { return h('th', { style: 'padding:7px 8px;text-align:left;font-size:12px;color:#6b7280;border-bottom:1px solid #e5e7eb;' }, t) }))].concat(rows)),
      ])
    }

    // ---- 大屏模式 ----
    function bigScreen() {
      var byKey = {}; metrics.value.forEach(function (m) { byKey[m.key] = m })
      var cards = metrics.value.filter(function (m) { return m.status !== 'neutral' || m.value !== null }).map(function (m) {
        var col = m.status === 'good' ? '#22c55e' : m.status === 'bad' ? '#ef4444' : m.status === 'warn' ? '#f59e0b' : '#38bdf8'
        return h('div', { style: 'flex:1;min-width:180px;background:rgba(255,255,255,.04);border:1px solid rgba(56,189,248,.25);border-radius:14px;padding:20px;' }, [
          h('div', { style: 'font-size:16px;color:#94a3b8;' }, m.label),
          h('div', { style: 'font-size:40px;font-weight:800;color:' + col + ';margin:10px 0;text-shadow:0 0 12px ' + col + '55;' }, fmtVal(m)),
          m.reached_pct != null ? h('div', { style: 'font-size:14px;color:#64748b;' }, '达成 ' + m.reached_pct + '%') : null,
        ])
      })
      return h('div', { style: 'position:fixed;inset:0;z-index:99999;background:radial-gradient(circle at 30% 20%,#0f172a,#020617);color:#e2e8f0;padding:28px;overflow:auto;' }, [
        h('div', { style: 'display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;' }, [
          h('div', { style: 'font-size:26px;font-weight:800;color:#38bdf8;' }, 'CenkorProcess 经营大屏'),
          h('div', { style: 'font-size:14px;color:#64748b;' }, '近' + days.value + '天 · ' + new Date().toLocaleString() + '　',
            h('button', { style: 'padding:6px 14px;border-radius:6px;border:1px solid #334155;background:#1e293b;color:#e2e8f0;cursor:pointer;', onClick: toggleBig }, '退出大屏')),
        ]),
        h('div', { style: 'display:flex;flex-wrap:wrap;gap:14px;' }, cards),
        h('div', { style: 'margin-top:24px;font-size:18px;color:#38bdf8;font-weight:700;' }, '风险告警'),
        h('div', { style: 'margin-top:8px;' }, (alerts.value || []).slice(0, 12).map(function (x) {
          return h('div', { style: 'padding:8px 0;border-bottom:1px solid rgba(148,163,184,.15);font-size:15px;color:' + (x.level === 'danger' ? '#f87171' : '#fbbf24') + ';' }, '[' + x.type + '] ' + x.text)
        })),
      ])
    }

    // ---- 工具栏 ----
    function toolbar() {
      function dbtn(d, label) { return h('button', { style: 'padding:6px 12px;border-radius:6px;cursor:pointer;font-size:13px;margin-right:6px;border:1px solid ' + (days.value === d ? '#2563eb' : '#e5e7eb') + ';background:' + (days.value === d ? '#eff6ff' : '#fff') + ';color:' + (days.value === d ? '#2563eb' : '#374151') + ';', onClick: function () { days.value = d } }, label) }
      return h('div', { style: 'background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:14px;margin-bottom:14px;display:flex;flex-wrap:wrap;align-items:center;gap:4px;' }, [
        dbtn(7, '近7天'), dbtn(30, '近30天'), dbtn(90, '近90天'),
        h('button', { style: 'padding:6px 12px;border-radius:6px;cursor:pointer;font-size:13px;margin-right:6px;border:1px solid #e5e7eb;background:#fff;color:#374151;', onClick: refresh }, '刷新'),
        h('button', { style: 'padding:6px 12px;border-radius:6px;cursor:pointer;font-size:13px;margin-right:6px;border:1px solid #e5e7eb;background:' + (showTargets.value ? '#eff6ff' : '#fff') + ';color:' + (showTargets.value ? '#2563eb' : '#374151') + ';', onClick: function () { showTargets.value = !showTargets.value } }, '目标设置'),
        h('button', { style: 'padding:6px 12px;border-radius:6px;cursor:pointer;font-size:13px;border:1px solid #0f172a;background:#0f172a;color:#fff;', onClick: toggleBig }, '进入大屏模式'),
        err.value ? h('span', { style: 'color:#dc2626;font-size:13px;margin-left:10px;' }, err.value) : null,
      ])
    }

    return function () {
      return h('div', { style: 'padding:16px;max-width:1280px;' }, [
        h('h2', { style: 'margin:0 0 12px;font-size:20px;' }, '经营驾驶舱与数据大屏'),
        toolbar(),
        big.value ? bigScreen() : h('div', null, [targetsPanel(), cockpit(), trendChart(), alertsList()]),
      ])
    }
  } }

  window.__registerExtension({
    key: 'dashboard_report',
    menus: [{ title: '经营驾驶舱', path: '/ext/dashboard-report', icon: 'DataBoard', permission: 'ext.dashboard_report.view' }],
    routes: [{ path: '/ext/dashboard-report', name: 'dashboard_report', component: App }],
    locales: { 'zh-CN': { dashboard_report: '经营驾驶舱' }, 'en-US': { dashboard_report: 'BI Cockpit' } },
  })
})()
