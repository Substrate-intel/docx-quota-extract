// smoke_front_lvse.mjs —— 渲染级冒烟（坑 34 根治：冒烟必须验证渲染，非文件存在）
// 用最小 DOM stub 执行 web/index.html 的内联脚本：启动链 buildTree→bindTree→show("gs")
// →refreshCounts 必须无异常完成，main 不得停留在「加载中…」；再逐个调用关键视图路由。
// 用法：node scripts/smoke_front_lvse.mjs
import { readFileSync } from "fs";

const html = readFileSync(new URL("../web/index.html", import.meta.url), "utf-8");const m = html.match(/<script>([\s\S]*)<\/script>/);
if (!m) { console.error("FAIL: 未找到内联 script"); process.exit(1); }
const js = m[1];

// ---------- 最小 DOM stub ----------
function makeEl() {
  const el = {
    _html: "", textContent: "", style: {}, title: "", dataset: {}, value: "",
    children: [], classList: { add(){}, remove(){}, toggle(){}, contains(){ return false; } },
    addEventListener(){}, appendChild(){}, querySelector(){ return makeEl(); },
    querySelectorAll(){ return []; }, click(){},
  };
  Object.defineProperty(el, "innerHTML", {
    get(){ return el._html; },
    set(v){ el._html = v; /* innerHTML 赋值时按标签粗分 children */ el.children = (String(v).match(/<div|<tr|<h3/g) || []).map(() => makeEl()); },
  });
  return el;
}
const els = {};
function get(sel) {
  if (!els[sel]) els[sel] = makeEl();
  return els[sel];
}
const document = {
  querySelector: (s) => get(s),
  querySelectorAll: () => [],
  createElement: () => makeEl(),
};
const localStorage = { getItem: () => null, setItem(){}, };
const window = { innerWidth: 1200, addEventListener(){} };
const URLStub = { createObjectURL: () => "", revokeObjectURL(){} };
const Blob = class {};

// ---------- 执行内联脚本 ----------
const results = [];
function check(name, fn) {
  try { fn(); results.push(["PASS", name]); }
  catch (e) { results.push(["FAIL", name + " :: " + e.message]); }
}

const ctx = { document, localStorage, window, URL: URLStub, Blob, console };
let DATA, GS_TYPE, buildTree, show, REVIEW, S;
try {
  const run = new Function("document", "localStorage", "window", "URL", "Blob", js +
    "; return { DATA, GS_TYPE, buildTree, show, REVIEW, S };");
  ({ DATA, GS_TYPE, buildTree, show, REVIEW, S } = run(document, localStorage, window, URLStub, Blob));
  results.push(["PASS", "脚本整体执行（启动链完成，无未捕获异常）"]);
} catch (e) {
  console.error("FAIL: 脚本执行抛异常 →", e.stack.split("\n").slice(0, 3).join(" | "));
  process.exit(1);
}

// ---------- 契约断言 ----------
check("DATA.stats 齐全（v1 崩溃点）", () => {
  if (!DATA.stats || !DATA.stats.h || !DATA.stats.h.H1) throw new Error("stats.h 缺失");
});
check("DATA.sections 非空且 block_type 齐全（v1 崩溃点）", () => {
  if (!DATA.sections.length) throw new Error("sections 空");
  for (const s of DATA.sections) if (!s.block_type) throw new Error("section 无 block_type");
});
check("GS_TYPE 判定", () => { if (GS_TYPE !== "册说明") throw new Error("GS_TYPE=" + GS_TYPE); });
check("main 已渲染非加载中（v1 症状）", () => {
  const h = get("#main").innerHTML;
  if (!h || h.includes("加载中")) throw new Error("main 停留在加载中");
});
check("章节树 4 章全部进树", () => {
  if (DATA.chapters.length !== 4) throw new Error("chapters=" + DATA.chapters.length);
  for (const c of DATA.chapters)
    if (c.six_layer_status !== "全六层已放大") throw new Error(c.chapter_code + " 未标记放大");
});
check("树 HTML 渲染含 4 章", () => {
  const t = get("#tree").innerHTML;
  for (const c of DATA.chapters)
    if (!t.includes("ch:" + c.chapter_code)) throw new Error("树缺章 " + c.chapter_code);
});
check("487 子目全部有 node_id 归属", () => {
  const bad = DATA.items.filter(i => !i.node_id);
  if (bad.length) throw new Error(bad.length + " 条无 node_id，如 " + bad[0].item_code);
});
check("REVIEW 人工核对清单构建", () => {
  const n = REVIEW.fail.length + REVIEW.unmatched.length + REVIEW.units.length + REVIEW.mids.length;
  if (n < 16) throw new Error("REVIEW=" + n + "（期望≥16 见表单位）");
});

// ---------- 视图路由逐一执行 ----------
// stub 预置：review 视图 paint() 读 #main .chip.on 的 dataset.c（真实浏览器由渲染 DOM 提供）
get("#main .chip.on").dataset = { c: "all" };
const views = [
  ["gs 册说明视图", () => show("gs")],
  ["toc 目录视图", () => show("toc")],
  ["章视图 ch:012001", () => show("ch:012001")],
  ["层视图 layer:12001:items（定额子目表）", () => show("layer:12001:items")],
  ["层视图 layer:12001:sm（章节说明）", () => show("layer:12001:sm")],
  ["层视图 layer:12001:js（计算规则）", () => show("layer:12001:js")],
  ["层视图 layer:12004:fb（附表）", () => show("layer:12004:fb")],
  ["review 人工核对", () => show("review")],
  ["issues 疑点清单", () => show("issues")],
  ["errata 勘误（空）", () => show("errata")],
  ["price 价格库（空）", () => show("price")],
  ["derive 缺价反推（空）", () => show("derive")],
  ["item:20-10 子目详情弹窗", () => show("item:20-10")],
];
for (const [name, fn] of views) check(name, fn);

// ---------- 结果 ----------
const fails = results.filter(r => r[0] === "FAIL");
for (const [st, name] of results) console.log(st === "PASS" ? " ✓" : " ✗", name);
console.log(fails.length ? `\n冒烟 FAIL ${fails.length}/${results.length}` : `\n冒烟全绿 ${results.length}/${results.length}`);
process.exit(fails.length ? 1 : 0);
