/*
 * 订单与生产计划（order_planning）前端插件 —— 销售订单 / 生产计划（含齐套·下达）/ 分配发货
 * 协议：window.__registerExtension({ key, menus, routes, locales })
 * 原生 Vue.h + 内联渲染；后端前缀 /api/extensions/order_planning，主数据取核心 /api/v1
 * 说明：需宿主前端「扩展动态加载器」就位后方能渲染（当前 cenkor-process 管理端尚未内置该加载器）。
 */
;(function () {
  var Vue = window.Vue
  if (!Vue || !window.__registerExtension) { console.warn('[order_planning] 宿主未提供注册桥，跳过注册'); return }
  var h = Vue.h, ref = Vue.ref, reactive = Vue.reactive, computed = Vue.computed, onMounted = Vue.onMounted
  var API = '/extensions/order_planning', CORE = '/v1', PREFIX = '/api'
  var HOST = window.__cenkorHost

  function token() { return sessionStorage.getItem('cenkormes_admin_token') || localStorage.getItem('cenkormes_admin_token') || '' }
  async function req(method, base, path, body, params) {
    // 优先走宿主请求桥（统一鉴权/信封/401 处理，path 相对 /api）；
    // 兼容 sessionStorage/localStorage 两种 token 存储，避免直读 localStorage 拿不到 token。
    if (HOST && typeof HOST.request === 'function') {
      return await HOST.request(method, base + path, body, params)
    }
    // 回退：无宿主桥时原生 fetch + 手动带 token、解信封
    var qs = params ? ('?' + new URLSearchParams(params).toString()) : ''
    var heads = { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token() }
    var hasBody = method !== 'GET' && method !== 'DELETE' && body
    var resp = await fetch(PREFIX + base + path + qs, { method: method, headers: heads, body: hasBody ? JSON.stringify(body) : undefined })
    var j = await resp.json().catch(function () { return {} })
    if (j && j.code && j.code !== 200) { throw new Error(j.msg || ('业务错误 ' + j.code)) }
    if (!resp.ok) { throw new Error((j && j.detail) || ('请求失败 ' + resp.status)) }
    return j.data
  }
  var extGet = function (p, q) { return req('GET', API, p, null, q) }
  var extPost = function (p, b, q) { return req('POST', API, p, b || {}, q) }
  var extPut = function (p, b) { return req('PUT', API, p, b || {}) }
  var extDelete = function (p) { return req('DELETE', API, p) }
  var coreGet = function (p, q) { return req('GET', CORE, p, null, q) }

  var card = 'background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:16px;margin-bottom:14px;'
  var th = 'padding:9px 8px;text-align:left;font-size:13px;color:#6b7280;border-bottom:1px solid #e5e7eb;white-space:nowrap;'
  var td = 'padding:9px 8px;font-size:14px;border-bottom:1px solid #f1f5f9;'
  var inp = 'padding:7px 10px;border:1px solid #d1d5db;border-radius:6px;font-size:14px;margin-right:8px;'
  function btn(label, onClick, kind) {
    var base = 'padding:6px 12px;border-radius:6px;border:1px solid transparent;cursor:pointer;font-size:13px;margin-right:6px;'
    var st = kind === 'active' ? 'background:#eff6ff;color:#2563eb;border-color:#bfdbfe;'
      : kind === 'primary' ? 'background:#2563eb;color:#fff;border-color:#2563eb;'
      : kind === 'danger' ? 'background:#fef2f2;color:#dc2626;border-color:#fecaca;'
      : 'background:#fff;color:#374151;border-color:#e5e7eb;'
    return h('button', { style: base + st, onClick: onClick }, label)
  }
  var ST = { draft: '草稿', confirmed: '已确认', released: '已下达', in_production: '生产中', completed: '已完成', partial_shipped: '部分发货', shipped: '已发货', closed: '已关闭', cancelled: '已取消' }
  function statusTag(s) { return h('span', { style: 'padding:2px 8px;border-radius:9999px;font-size:12px;background:#f3f4f6;color:#374151;' }, ST[s] || s) }
  function sel(options, value, onPick, ph) {
    return h('select', { style: inp, onChange: function (e) { onPick(e.target.value) } },
      [h('option', { value: '' }, ph || '请选择')].concat(options.map(function (o) { return h('option', { value: o.value, selected: String(o.value) === String(value) }, o.label) })))
  }

  var Page = {
    name: 'OrderPlanningPage',
    setup: function () {
      var tab = ref('orders'), err = ref(''), busy = ref(false)
      var recipes = ref([]), materials = ref([]), warehouses = ref([])
      var orders = ref([]), plans = ref([])
      var of = reactive({ customer_name: '', material_id: '', qty: '', uom_id: '' })
      var orderLines = ref([{ material_id: '', qty: '' }])
      var detail = ref(null)
      var pf = reactive({ source_type: 'mto', recipe_id: '', planned_qty: '', warehouse_id: '' })
      var kit = ref(null), shipPanel = ref(null)
      var ss = ref([]), sugg = ref(null), ssBusy = ref(false)
      var ssf = reactive({ material_id: '', warehouse_id: '', min_qty: '', max_qty: '' })

      async function loadMasters() {
        try {
          recipes.value = (await coreGet('/recipes') || []).map(function (r) { return { id: r.id, code: r.code, name: r.name, product_material_id: r.product_material_id, base_uom_id: r.base_uom_id } })
          materials.value = (await coreGet('/materials') || [])
          warehouses.value = (await coreGet('/warehouses') || [])
        } catch (e) { err.value = '主数据加载失败：' + e.message }
      }
      async function loadOrders() { try { orders.value = await extGet('/orders') || [] } catch (e) { err.value = e.message } }
      async function loadPlans() { try { plans.value = await extGet('/plans') || [] } catch (e) { err.value = e.message } }

      async function loadSafetyStock() { try { ss.value = await extGet('/safety-stock') || [] } catch (e) { err.value = e.message } }
      async function loadSuggestions() { err.value = ''; sugg.value = null; try { sugg.value = await extGet('/mts-suggestions') } catch (e) { err.value = e.message } }
      async function scanAlert() { err.value = ''; try { var d = await extPost('/safety-stock/scan-alert'); alert(d.count ? ('扫描完成：' + d.count + ' 个成品低于安全库存，已投递备货预警') : '扫描完成：当前库存均高于安全库存'); await loadSuggestions() } catch (e) { err.value = e.message } }
      async function saveSS() {
        err.value = ''; if (!ssf.material_id || !ssf.warehouse_id || !ssf.max_qty) { err.value = '成品/仓库/目标库存必填'; return }
        ssBusy.value = true
        try { await extPut('/safety-stock', { material_id: Number(ssf.material_id), warehouse_id: Number(ssf.warehouse_id), min_qty: String(ssf.min_qty || 0), max_qty: String(ssf.max_qty) }); ssf.material_id = ''; ssf.warehouse_id = ''; ssf.min_qty = ''; ssf.max_qty = ''; await loadSafetyStock(); await loadSuggestions() }
        catch (e) { err.value = e.message } finally { ssBusy.value = false }
      }
      async function delSS(r) { if (!confirm('删除该备货策略？')) return; try { await extDelete('/safety-stock/' + r.id); await loadSafetyStock(); await loadSuggestions() } catch (e) { err.value = e.message } }
      async function genMts(list) {
        err.value = ''; if (!list || !list.length) { err.value = '无可生成项'; return }
        try { var d = await extPost('/generate-mts', { items: list.map(function (x) { return { material_id: x.material_id, warehouse_id: x.warehouse_id, qty: x.suggested_qty, recipe_id: x.recipe_id, uom_id: x.uom_id } }) }); alert('已生成 ' + d.count + ' 张草稿 MTS 计划，请到「生产计划」齐套/下达'); sugg.value = null; await loadSafetyStock() }
        catch (e) { err.value = e.message }
      }
      async function syncPlan(p) { try { var d = await extPost('/plans/' + p.id + '/sync-status'); alert('计划状态：' + (ST[d.status] || d.status)); await loadPlans() } catch (e) { err.value = e.message } }
      async function delPlan(p) { if (!confirm('删除草稿计划 ' + p.plan_no + '？')) return; try { await extDelete('/plans/' + p.id); await loadPlans() } catch (e) { err.value = e.message } }
      async function delOrder(o) { if (!confirm('删除订单 ' + o.order_no + '？')) return; try { await extDelete('/orders/' + o.id); await loadOrders() } catch (e) { err.value = e.message } }

      function addLine() { orderLines.value.push({ material_id: '', qty: '' }) }
      function removeLine(i) { if (orderLines.value.length > 1) orderLines.value.splice(i, 1) }
      async function createOrder() {
        err.value = ''
        if (!of.customer_name) { err.value = '客户名称必填'; return }
        var items = orderLines.value.filter(function (l) { return l.material_id && Number(l.qty) > 0 }).map(function (l) { return { material_id: Number(l.material_id), qty: String(l.qty) } })
        if (!items.length) { err.value = '至少一行有效的成品 + 数量'; return }
        busy.value = true
        try { await extPost('/orders', { customer_name: of.customer_name, items: items }); of.customer_name = ''; orderLines.value = [{ material_id: '', qty: '' }]; await loadOrders() }
        catch (e) { err.value = e.message } finally { busy.value = false }
      }
      async function openDetail(o) { err.value = ''; detail.value = { order: o, data: null }; try { detail.value.data = await extGet('/orders/' + o.id) } catch (e) { err.value = e.message } }
      function closeDetail() { detail.value = null }
      async function confirmOrder(o) { try { await extPost('/orders/' + o.id + '/confirm'); await loadOrders() } catch (e) { err.value = e.message } }

      async function createPlan() {
        err.value = ''; if (!pf.recipe_id || !pf.planned_qty) { err.value = '配方/数量必填'; return }
        var r = recipes.value.find(function (x) { return String(x.id) === String(pf.recipe_id) }) || {}
        busy.value = true
        try {
          await extPost('/plans', { source_type: pf.source_type, recipe_id: Number(pf.recipe_id), material_id: r.product_material_id, planned_qty: String(pf.planned_qty), uom_id: r.base_uom_id, warehouse_id: pf.warehouse_id ? Number(pf.warehouse_id) : null })
          pf.recipe_id = ''; pf.planned_qty = ''; await loadPlans()
        } catch (e) { err.value = e.message } finally { busy.value = false }
      }
      async function runKitting(p) { err.value = ''; kit.value = { plan: p, data: null }; try { kit.value.data = await extGet('/plans/' + p.id + '/kitting') } catch (e) { err.value = e.message } }
      async function releasePlan(p) {
        err.value = ''; if (!confirm('确认下达计划 ' + p.plan_no + '？将生成核心生产批次。')) return
        try { var d = await extPost('/plans/' + p.id + '/release', {}, { force: 'true' }); alert('已下达，批次号：' + d.batch_no); await loadPlans() } catch (e) { err.value = e.message }
      }

      async function openShip(o) { err.value = ''; shipPanel.value = { order: o, rows: null }; try { shipPanel.value.rows = await extGet('/orders/' + o.id + '/allocatable-lots') } catch (e) { err.value = e.message } }
      async function allocateAndShip(row, lot) {
        err.value = ''
        try {
          var al = await extPost('/orders/' + shipPanel.value.order.id + '/allocate', [{ order_item_id: row.order_item_id, lot_id: lot.lot_id, qty: String(lot.qty) }])
          await extPost('/allocations/' + al.created[0] + '/ship')
          await openShip(shipPanel.value.order); await loadOrders()
        } catch (e) { err.value = e.message }
      }

      function switchTab(t) { tab.value = t; err.value = ''; if (t === 'orders') loadOrders(); if (t === 'plans') loadPlans(); if (t === 'mts') { loadSafetyStock(); loadSuggestions() } }

      // ---- 订单视图 ----
      function renderOrders() {
        return h('div', { style: card }, [
          h('div', { style: 'font-weight:600;margin-bottom:10px;' }, '新建销售订单（MTO · 支持多行明细）'),
          h('div', { style: 'display:flex;gap:8px;align-items:center;margin-bottom:8px;' }, [
            h('span', { style: 'font-size:13px;color:#6b7280;' }, '客户名称'),
            h('input', { style: inp, placeholder: '客户名称', value: of.customer_name, onInput: function (e) { of.customer_name = e.target.value } }),
          ]),
          h('table', { style: 'width:100%;border-collapse:collapse;' }, [
            h('thead', {}, h('tr', {}, ['成品物料', '数量', '操作'].map(function (x) { return h('th', { style: th }, x) }))),
            h('tbody', {}, orderLines.value.map(function (ln, i) {
              return h('tr', {}, [
                h('td', { style: td }, sel(materials.value.map(function (m) { return { value: m.id, label: m.code + ' ' + m.name } }), ln.material_id, function (v) { ln.material_id = v }, '选择成品')),
                h('td', { style: td }, h('input', { style: inp, type: 'number', placeholder: '数量', value: ln.qty, onInput: function (e) { ln.qty = e.target.value } })),
                h('td', { style: td }, orderLines.value.length > 1 ? btn('删除行', function () { removeLine(i) }, 'danger') : null),
              ])
            })),
          ]),
          h('div', { style: 'margin-top:8px;display:flex;gap:6px;' }, [btn('加一行', addLine), btn(busy.value ? '提交中…' : '创建订单', createOrder, 'primary')]),
        ])
      }
      function ordersTable() {
        if (!orders.value.length) return h('div', { style: 'color:#9ca3af;padding:10px;' }, '暂无订单')
        return h('table', { style: 'width:100%;border-collapse:collapse;' }, [
          h('thead', {}, h('tr', {}, ['订单号', '客户', '交期', '状态', '操作'].map(function (x) { return h('th', { style: th }, x) }))),
          h('tbody', {}, orders.value.map(function (o) {
            return h('tr', {}, [
              h('td', { style: td }, o.order_no), h('td', { style: td }, o.customer_name),
              h('td', { style: td }, o.due_date || '—'), h('td', { style: td }, statusTag(o.status)),
              h('td', { style: td }, [
                btn('详情', function () { openDetail(o) }),
                o.status === 'draft' ? btn('确认', function () { confirmOrder(o) }, 'primary') : null,
                h('button', { style: 'padding:6px 12px;border-radius:6px;border:1px solid #e5e7eb;cursor:pointer;font-size:13px;background:#fff;color:#374151;', onClick: function () { openShip(o) } }, '分配/发货'),
                (o.status === 'draft' || o.status === 'confirmed' || o.status === 'cancelled') ? btn('删除', function () { delOrder(o) }, 'danger') : null,
              ]),
            ])
          })),
        ])
      }
      function renderShip() {
        if (!shipPanel.value) return null
        var sp = shipPanel.value
        return h('div', { style: card }, [
          h('div', { style: 'font-weight:600;margin-bottom:10px;' }, '订单 ' + sp.order.order_no + ' · 可发货成品批次'),
          !sp.rows ? h('div', {}, '加载中…') : h('div', {}, sp.rows.map(function (row) {
            return h('div', { style: 'margin-bottom:10px;' }, [
              h('div', { style: 'font-size:13px;color:#6b7280;' }, '订单行 #' + row.order_item_id + ' 需求 ' + row.need),
              row.lots.length ? h('table', { style: 'width:100%;border-collapse:collapse;margin-top:4px;' }, [
                h('thead', {}, h('tr', {}, ['批次号', '可用量', '效期', '操作'].map(function (x) { return h('th', { style: th }, x) }))),
                h('tbody', {}, row.lots.map(function (lot) {
                  return h('tr', {}, [h('td', { style: td }, lot.lot_no), h('td', { style: td }, lot.qty), h('td', { style: td }, lot.expiry_at || '—'),
                    h('td', { style: td }, btn('分配并发货', function () { allocateAndShip(row, lot) }, 'primary'))])
                })),
              ]) : h('div', { style: 'color:#9ca3af;font-size:13px;' }, '无已放行足量批次（需先经生产下达并完成过账放行）'),
            ])
          })),
        ])
      }

      // ---- 计划视图 ----
      function renderPlans() {
        return h('div', { style: card }, [
          h('div', { style: 'font-weight:600;margin-bottom:10px;' }, '新建生产计划（接单 MTO / 备货 MTS）'),
          h('div', { style: 'display:flex;flex-wrap:wrap;gap:4px;align-items:center;' }, [
            sel([{ value: 'mto', label: 'MTO 接单' }, { value: 'mts', label: 'MTS 备货' }], pf.source_type, function (v) { pf.source_type = v }),
            sel(recipes.value.map(function (r) { return { value: r.id, label: r.code + ' ' + r.name } }), pf.recipe_id, function (v) { pf.recipe_id = v }, '配方(须已发布)'),
            h('input', { style: inp, type: 'number', placeholder: '计划数量', value: pf.planned_qty, onInput: function (e) { pf.planned_qty = e.target.value } }),
            sel(warehouses.value.map(function (w) { return { value: w.id, label: w.name } }), pf.warehouse_id, function (v) { pf.warehouse_id = v }, '仓库'),
            btn(busy.value ? '提交中…' : '创建计划', createPlan, 'primary'),
          ]),
        ])
      }
      function plansTable() {
        if (!plans.value.length) return h('div', { style: 'color:#9ca3af;padding:10px;' }, '暂无计划')
        return h('table', { style: 'width:100%;border-collapse:collapse;' }, [
          h('thead', {}, h('tr', {}, ['计划单号', '来源', '成品', '数量', '交期', '状态', '操作'].map(function (x) { return h('th', { style: th }, x) }))),
          h('tbody', {}, plans.value.map(function (p) {
            return h('tr', {}, [
              h('td', { style: td }, p.plan_no), h('td', { style: td }, p.source_type.toUpperCase()),
              h('td', { style: td }, (p.material_code || '') + ' ' + (p.material_name || '')), h('td', { style: td }, p.planned_qty),
              h('td', { style: td }, p.due_date || '—'), h('td', { style: td }, statusTag(p.status)),
              h('td', { style: td }, [
                p.status === 'draft' ? btn('齐套', function () { runKitting(p) }) : null,
                p.status === 'draft' ? btn('下达', function () { releasePlan(p) }, 'primary') : null,
                (p.status === 'released' || p.status === 'in_production') ? btn('同步状态', function () { syncPlan(p) }) : null,
                p.status === 'draft' ? btn('删除', function () { delPlan(p) }, 'danger') : null,
              ]),
            ])
          })),
        ])
      }
      function renderKit() {
        if (!kit.value) return null
        var d = kit.value.data
        return h('div', { style: card }, [
          h('div', { style: 'font-weight:600;margin-bottom:10px;' }, '齐套预检 · ' + kit.value.plan.plan_no + (d ? (d.enough ? ' （✔ 齐套）' : ' （⚠ 有缺料）') : '')),
          !d ? h('div', {}, '计算中…') : h('table', { style: 'width:100%;border-collapse:collapse;' }, [
            h('thead', {}, h('tr', {}, ['物料', '需求', '可用', '缺口'].map(function (x) { return h('th', { style: th }, x) }))),
            h('tbody', {}, d.lines.map(function (l) {
              return h('tr', {}, [h('td', { style: td }, '物料#' + l.material_id), h('td', { style: td }, l.need_qty), h('td', { style: td }, l.available_qty),
                h('td', { style: td + (Number(l.shortage_qty) > 0 ? ' color:#dc2626;font-weight:600;' : '') }, l.shortage_qty)])
            })),
          ]),
        ])
      }

      // ---- 备货(MTS) 视图 ----
      function renderSS() {
        return h('div', { style: card }, [
          h('div', { style: 'font-weight:600;margin-bottom:10px;' }, '安全库存备货策略（MTS 驱动源）'),
          h('div', { style: 'display:flex;flex-wrap:wrap;gap:4px;align-items:center;margin-bottom:10px;' }, [
            sel(materials.value.map(function (m) { return { value: m.id, label: m.code + ' ' + m.name } }), ssf.material_id, function (v) { ssf.material_id = v }, '成品物料'),
            sel(warehouses.value.map(function (w) { return { value: w.id, label: w.name } }), ssf.warehouse_id, function (v) { ssf.warehouse_id = v }, '仓库'),
            h('input', { style: inp, type: 'number', placeholder: '最低 min', value: ssf.min_qty, onInput: function (e) { ssf.min_qty = e.target.value } }),
            h('input', { style: inp, type: 'number', placeholder: '目标 max', value: ssf.max_qty, onInput: function (e) { ssf.max_qty = e.target.value } }),
            btn(ssBusy.value ? '保存中…' : '保存策略', saveSS, 'primary'),
            btn('扫描并预警', scanAlert),
            btn('刷新备货建议', loadSuggestions),
          ]),
          !ss.value.length ? h('div', { style: 'color:#9ca3af;' }, '暂无备货策略，请先添加') : h('table', { style: 'width:100%;border-collapse:collapse;' }, [
            h('thead', {}, h('tr', {}, ['成品', '仓库', '最低', '目标', '现有可用', '操作'].map(function (x) { return h('th', { style: th }, x) }))),
            h('tbody', {}, ss.value.map(function (r) {
              return h('tr', {}, [
                h('td', { style: td }, (r.material_code || '') + ' ' + (r.material_name || '')),
                h('td', { style: td }, r.warehouse_name || ('仓库#' + r.warehouse_id)),
                h('td', { style: td }, r.min_qty), h('td', { style: td }, r.max_qty),
                h('td', { style: td + (Number(r.on_hand) < Number(r.min_qty) ? ' color:#dc2626;font-weight:600;' : '') }, r.on_hand),
                h('td', { style: td }, btn('删除', function () { delSS(r) }, 'danger')),
              ])
            })),
          ]),
        ])
      }
      function renderSugg() {
        if (!sugg.value) return null
        var items = sugg.value.items || []
        return h('div', { style: card }, [
          h('div', { style: 'font-weight:600;margin-bottom:10px;' }, '备货建议（现有 < 最低 → 建议补到目标）' + (items.length ? '' : ' · 当前无需备货')),
          !items.length ? null : h('div', {}, [
            h('table', { style: 'width:100%;border-collapse:collapse;' }, [
              h('thead', {}, h('tr', {}, ['成品', '现有', '最低', '建议补货', '配方', '操作'].map(function (x) { return h('th', { style: th }, x) }))),
              h('tbody', {}, items.map(function (x) {
                return h('tr', {}, [
                  h('td', { style: td }, (x.material_code || '') + ' ' + (x.material_name || '')),
                  h('td', { style: td }, x.on_hand), h('td', { style: td }, x.min_qty),
                  h('td', { style: td + ' color:#2563eb;font-weight:600;' }, x.suggested_qty),
                  h('td', { style: td }, x.can_plan ? (x.recipe_code || ('配方#' + x.recipe_id)) : h('span', { style: 'color:#dc2626;' }, '无已发布配方')),
                  h('td', { style: td }, x.can_plan ? btn('生成MTS计划', function () { genMts([x]) }, 'primary') : null),
                ])
              })),
            ]),
            h('div', { style: 'margin-top:10px;' }, btn('全部可备货项生成计划', function () { genMts(items.filter(function (x) { return x.can_plan })) }, 'primary')),
          ]),
        ])
      }

      function renderDetail() {
        if (!detail.value) return null
        var d = detail.value.data
        return h('div', { style: card + 'border-color:#bfdbfe;' }, [
          h('div', { style: 'display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;' }, [
            h('div', { style: 'font-weight:600;' }, '订单详情 · ' + detail.value.order.order_no),
            btn('关闭', closeDetail),
          ]),
          !d ? h('div', {}, '加载中…') : h('div', {}, [
            h('div', { style: 'font-size:13px;color:#374151;margin-bottom:8px;' }, '客户：' + (d.order.customer_name || '—') + '　状态：' + (ST[d.order.status] || d.order.status) + '　交期：' + (d.order.due_date || '—')),
            h('div', { style: 'font-weight:600;font-size:13px;margin:6px 0;' }, '订单明细'),
            h('table', { style: 'width:100%;border-collapse:collapse;' }, [
              h('thead', {}, h('tr', {}, ['成品', '数量', '已发'].map(function (x) { return h('th', { style: th }, x) }))),
              h('tbody', {}, (d.items || []).map(function (it) {
                return h('tr', {}, [h('td', { style: td }, (it.material_code || '') + ' ' + (it.material_name || '')), h('td', { style: td }, it.qty), h('td', { style: td }, it.delivered_qty)])
              })),
            ]),
            h('div', { style: 'font-weight:600;font-size:13px;margin:10px 0 6px;' }, '关联生产计划'),
            (d.plans && d.plans.length) ? h('table', { style: 'width:100%;border-collapse:collapse;' }, [
              h('thead', {}, h('tr', {}, ['计划单号', '数量', '状态'].map(function (x) { return h('th', { style: th }, x) }))),
              h('tbody', {}, d.plans.map(function (p) { return h('tr', {}, [h('td', { style: td }, p.plan_no), h('td', { style: td }, p.planned_qty), h('td', { style: td }, statusTag(p.status))]) })),
            ]) : h('div', { style: 'color:#9ca3af;font-size:13px;' }, '暂无关联计划'),
          ]),
        ])
      }

      onMounted(function () { loadMasters(); loadOrders() })
      return function () {
        return h('div', { style: 'padding:4px;' }, [
          h('div', { style: 'display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;' }, [
            h('h2', { style: 'margin:0;font-size:20px;' }, '订单与生产计划'),
            h('div', {}, [
              btn('销售订单', function () { switchTab('orders') }, tab.value === 'orders' ? 'active' : ''),
              btn('生产计划', function () { switchTab('plans') }, tab.value === 'plans' ? 'active' : ''),
              btn('备货(MTS)', function () { switchTab('mts') }, tab.value === 'mts' ? 'active' : ''),
            ]),
          ]),
          err.value ? h('div', { style: 'background:#fef2f2;color:#dc2626;padding:10px 14px;border-radius:8px;margin-bottom:14px;font-size:14px;' }, err.value) : null,
          tab.value === 'orders' ? h('div', {}, [renderOrders(), h('div', { style: card }, ordersTable()), renderShip(), renderDetail()]) : null,
          tab.value === 'plans' ? h('div', {}, [renderPlans(), h('div', { style: card }, plansTable()), renderKit()]) : null,
          tab.value === 'mts' ? h('div', {}, [renderSS(), renderSugg()]) : null,
        ])
      }
    },
  }

  window.__registerExtension({
    key: 'order_planning',
    menus: [
      { title: '订单与生产计划', i18nKey: 'menu.orderPlanning', path: '/ext/order-planning', icon: 'Tickets', permission: 'ext.order_planning.view' },
    ],
    routes: [{ path: '/ext/order-planning', name: 'ext-order-planning', component: Page }],
    locales: { zh: { menu: { orderPlanning: '订单与生产计划' } }, en: { menu: { orderPlanning: 'Order & Planning' } } },
  })
})()
