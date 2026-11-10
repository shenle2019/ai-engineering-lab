# Nuxt 框架与 Mealie 字段扩展二次开发

> 来源：python 山顶会三期 day11（`day11/day03.md` + `day11/Nuxt框架.md`）
> 定位：先用一份 Nuxt 速查把手头的前端看懂，再按"模型 → 迁移 → Schema → 接口 → 前端"五步做第一个字段扩展

## 总览

这节课分两半：前半是 Nuxt 框架的基础（定义、目录、路由、中间件、布局、自动导入），后半是二次开发的第一个实操——给 Recipe 加 `difficulty` 字段。前者的作用是"看得懂 Mealie 前端"，后者是"走通一条最小的全链路改造"。

## 1. 二次开发从哪里起步

课件给的原则：**不要一上来挑复杂度最高的需求**。熟悉项目后，优先从改 bug、删除/新增内容开始，前提是不破坏核心主业务和主要流程。这样做有两个好处：一是熟悉项目的代码风格与业务流转，二是能照葫芦画瓢，降低难度。

反面例子（"太重，以后再说"）：权限体系重构、复杂导入导出、批量任务编排。

## 2. Nuxt 是什么

Nuxt 是基于 Vue.js 的开源全栈框架，核心作用是简化 SSR（服务端渲染）、SSG（静态站点生成）和 SPA 的开发流程。设计理念是"约定优于配置"：路由、组件注册等不用手写。官方定位是"构建生产级 Vue 应用的框架"，底层是 Vue 3 + Vite + Nitro 服务器引擎，支持 TypeScript。

一句话类比：**Next.js 之于 React，就是 Nuxt 之于 Vue**。

版本对应关系要记清：

| Nuxt 版本 | Vue 版本 | 代码风格 |
| --- | --- | --- |
| Nuxt 2.x | Vue 2 | 选项式 API（Options API） |
| Nuxt 3/4 | Vue 3 | 组合式 API（Composition API） |

推荐直接学 Nuxt 4：基于 Vue 3 组合式 API、Vite 构建、内置 Nitro、自动导入更完善。

## 3. 核心特性与 Vue 的差别

五个核心特性：

| 特性 | 说明 |
| --- | --- |
| 多渲染模式 | SSR / SSG / 混合渲染 / SPA，按场景选 |
| 智能路由 | 基于文件系统自动生成，支持动态路由、嵌套路由 |
| 自动导入 | 组件、组合式函数免 import，直接使用 |
| 全栈能力 | 内置 `server/` 目录，可直接写 API 与服务器中间件 |
| 内置性能优化 | 代码分割、组件懒加载、静态资源缓存 |

与普通 Vue 项目的关键差异：

| 维度 | 传统 Vue | Nuxt |
| --- | --- | --- |
| SEO | 需额外配置 SSR，纯客户端渲染 SEO 差 | 开箱即用 SSR/SSG，返回完整 HTML |
| 路由 | 手写路由表 | `pages/` 目录自动生成 |
| 项目结构 | 自由组织，各人风格不同 | 约定式结构，标准化 |
| 构建 | 需手动配 Vite 优化 | 预设配置开箱即用 |
| 首屏 | 客户端运行时渲染，较慢 | SSR/SSG 预渲染，更快 |

适用场景：官网/营销站、内容平台（博客、新闻、文档）、电商（商品页要收录）、需要社交分享预览的应用。**不适用**：纯后台管理系统（无需 SEO，SPA 更简单）、高度交互的复杂动画应用（SSR 增加调试复杂度）。

## 4. 目录结构

Nuxt 3/4 的约定式目录（官方模板）：

```text
my-nuxt-demo/
├── .nuxt/                # 开发运行时目录，自动生成
├── app/
│   ├── components/       # 可复用组件，自动注册
│   ├── composables/      # 组合式函数，自动导入
│   ├── layouts/          # 布局组件
│   ├── middleware/       # 路由中间件
│   ├── pages/            # 页面，自动生成路由
│   ├── plugins/          # 插件，自动加载
│   ├── utils/            # 工具函数
│   ├── app.config.ts     # 应用配置（响应式共享）
│   ├── app.vue           # 根组件
│   └── error.vue         # 全局错误页
├── public/               # 原样复制的静态资源
├── server/               # 服务端代码（api / middleware / plugins / utils）
├── nuxt.config.ts        # 全局配置
├── package.json
└── tsconfig.json
```

几个容易混淆的点：

- `public/` 里的文件原样复制、可用根路径直接访问，适合 favicon、robots.txt 这类不需要构建处理的文件
- `server/api/` 下的文件会自动生成 API 路由
- `app.config.ts` 与 `nuxt.config.ts` 的分工：前者存运行时可共享的响应式配置（主题色等），后者是构建期全局配置

## 5. 路由机制

### 5.1 文件即路由

| pages 目录 | 路由地址 |
| --- | --- |
| `pages/index.vue` | `/` |
| `pages/about.vue` | `/about` |
| `pages/blog/index.vue` | `/blog` |
| `pages/blog/post.vue` | `/blog/post` |

导航用 `NuxtLink` 替代 `a` 标签：它渲染成 a 标签、做客户端跳转避免刷新，还会预加载目标页面资源。本质是 `<router-link>` 的高阶封装。

### 5.2 动态路由三种写法

| 写法 | 含义 | 示例 |
| --- | --- | --- |
| `[id].vue` | 普通动态参数 | `/user/1` |
| `[[name]].vue` | 参数可选 | 同时匹配 `/hello` 与 `/hello/张三` |
| `[...slug].vue` | 通配，捕获跨层级路径 | 404 页面 |

取参两种方式：模板里 `$route.params.id`；脚本里 `useRoute()` 拿到 route 对象后读 `route.params.id`（复杂场景、参数监听、类型提示更推荐这种做法）。

> Mealie 的菜谱详情页路径 `pages/g/[groupSlug]/r/[slug]/index.vue` 就是这套约定的直接体现：两级动态参数 + index 收尾。

### 5.3 嵌套路由与路由元信息

嵌套路由靠"父页面里放 `<NuxtPage />`"实现：`pages/blog/index.vue` 作为父级渲染公共部分，子目录页面通过 `<NuxtPage />` 出口渲染。

路由元信息用 `definePageMeta` 在页面里声明，常见字段：`title`、`layout`、`middleware`，也可以放自定义标记（如 `requiresAuth`、`requiresPermissions`）供中间件读取。

## 6. 路由中间件

中间件是导航前/中/后执行的代码，用于权限校验、路由拦截、数据预处理。三类都放在 `app/middleware/`：

| 类型 | 定义方式 | 作用范围 |
| --- | --- | --- |
| 全局中间件 | 文件名以 `.global.ts` 结尾 | 所有路由切换都执行，无需注册 |
| 页面中间件 | 文件名无后缀，页面里 `definePageMeta({ middleware: 'auth' })` 关联 | 仅指定页面及其子路由 |
| 布局中间件 | 在布局组件里通过 `definePageMeta` 关联 | 使用该布局的所有页面 |

典型写法：

```typescript
// app/middleware/auth.ts
export default defineNuxtRouteMiddleware((to, from) => {
  const isLogin = false
  if (!isLogin) {
    return navigateTo('/login')
  }
  return true
})
```

## 7. 布局与自动导入

### 7.1 布局

- `app/layouts/default.vue` 是默认布局，未指定布局的页面都用它；**不能删**，删了未指定布局的页面渲染不出来
- 自定义布局（如 `admin.vue`），页面用 `definePageMeta({ layout: 'admin' })` 指定；写 `layout: false` 表示不用任何布局
- 布局里**必须包含 `<NuxtPage />`**，否则页面内容没有出口
- 布局与页面传参：页面里 `useLayoutData({ activeMenu: 'dashboard' })` 传，布局里 `const { activeMenu } = useLayoutData()` 收

### 7.2 组件自动导入

`app/components/` 下的组件自动注册，规则：

- 文件名 PascalCase（`HelloWorld.vue` → `<HelloWorld />`）
- 子目录**自动拼目录前缀**：`components/user/LoginForm.vue` → `<UserLoginForm />`，`components/common/Button.vue` → `<CommonButton />`
- 文件名前加下划线（`_Unused.vue`）可排除自动导入
- 手动 import 优先级高于自动导入

Mealie 前端 `components/Domain/Recipe/` 这类目录能直接用 `<DomainRecipeXxx />` 之类的名字，正是这条规则在起作用。

### 7.3 组合式函数自动导入

`app/composables/` 下 `.ts/.js` 导出的函数自动导入。命名用 camelCase 且建议 `use` 开头（`useFormatDate`）。只有 `export` 出去的才会被自动导入。若要新增自动导入目录（如 `app/utils`），在 `nuxt.config.ts` 的 `imports.dirs` 里配置。

## 8. 第一个改造需求：给 Recipe 加 difficulty

字段值限定在 `easy` / `medium` / `hard` / `none`。选它作为第一轮扩展的四个理由：

1. **数据可见**：加完字段，接口和页面都能直接看到结果
2. **链路完整**：数据库 → Schema → 接口 → 前端，一条不缺
3. **风险低**：只是食谱的附加字段，不动 `Recipe` 的核心主流程
4. **可延伸**：以后能基于它做筛选、统计、推荐、AI 生成

## 9. 动手前先问六个问题

不要打开文件就写。先确认：

1. 字段要落库吗？→ 要
2. 只读还是支持创建/更新？→ 都要
3. 列表页要显示吗？→ 可以显示
4. 详情页要显示吗？→ 应该显示
5. 前端表单要能录入吗？→ 要
6. 影响查询/排序/筛选吗？→ 后续可以，第一版先不做

这六个答案直接决定改动顺序：

```text
1. 改 ORM 模型
2. 生成数据库迁移
3. 改 Schema
4. 检查接口收参与返回值
5. 补前端展示
```

## 10. 五步改造细节

### 10.1 模型层

文件：`mealie/db/models/recipe/recipe.py`。`RecipeModel` 本来就承载 `name`、`description`、`total_time`、`recipe_servings`、`rating` 这类主体字段，`difficulty` 直接加在这里：

```python
difficulty: Mapped[str | None] = mapped_column(sa.String, nullable=True, index=True)
```

设计理由：便于快速落地、不马上引入枚举兼容问题、兼容历史数据为空。改完要明确三件事：`recipes` 表多一列、允许为空、ORM 已认识这个字段。

### 10.2 数据迁移

模型只是代码层结构，表结构真正变化要靠迁移。`Taskfile.yml` 已有对应任务：

```powershell
uv run alembic --config mealie/alembic/alembic.ini revision --autogenerate -m "你的迁移说明"
# 或者
task py:migrate -- "add new column: recipes [difficulty]"
```

迁移文件核心两行：

```python
op.add_column("recipes", sa.Column("difficulty", sa.String(length=32), nullable=True))
op.drop_column("recipes", "difficulty")   # downgrade
```

四个检查点：表名对不对（`recipes`）、字段名与 ORM 一致、第一版允许为空（避免历史数据导致迁移失败）、`downgrade()` 不能省。

### 10.3 Schema 层

模型管"数据库怎么存"，Schema 管"接口怎么收、怎么返"。只改模型不改 Schema 的三种典型故障：

- 前端提交 `difficulty`，后端不接收
- 数据库有值，接口返回里没有这个字段
- 更新接口把字段丢掉

文件：`mealie/schema/recipe/recipe.py`。本次把 `difficulty` 加进 `RecipeSummary` 和 `Recipe`（列表与详情都能返回）。如果还要支持创建/更新，需继续检查创建接口与更新接口各自使用的 Schema。

### 10.4 路由与服务层

重点看三个文件：

```text
mealie/routes/recipe/recipe_crud_routes.py
mealie/routes/recipe/_base.py
mealie/services/recipe/recipe_service.py
```

确认三件事：创建菜谱收的是哪个 Schema、更新菜谱收的是哪个 Schema、`RecipeService` 在创建和更新时会不会把未知字段过滤掉。

### 10.5 前端层

Recipe 相关页面优先看这三处：

```text
frontend/pages/g/[groupSlug]/r/[slug]/index.vue   # 详情页
frontend/pages/g/[groupSlug]/r/create/new.vue     # 新建页
frontend/components/Domain/Recipe/                # 领域组件
```

最少做两件事：新建/编辑表单里加 `difficulty` 录入、详情页展示 `difficulty`。

## 关键知识清单

- 二次开发先做"动数据不动主流程"的小改动，权限重构、批量编排这类往后放
- Nuxt = Vue 的 Next.js：约定优于配置，SSR/SSG 开箱即用
- Nuxt2 配 Vue2 选项式 API，Nuxt3/4 配 Vue3 组合式 API
- `pages/` 出路由：`index.vue` → `/`，`[id].vue` 动态，`[[name]].vue` 可选，`[...slug].vue` 通配
- 中间件三类：`.global` 全局、无后缀页面级（`definePageMeta` 关联）、布局级
- 布局必须有 `<NuxtPage />`，`default.vue` 不能删；`layout: false` 可免布局
- 组件自动导入按 PascalCase，子目录拼前缀（`user/LoginForm.vue` → `<UserLoginForm />`）
- 加字段的顺序：ORM → 迁移 → Schema → 接口 → 前端，五步一步都不能跳
- 字段类型先用 `str | None` + `nullable=True`，别一上来搞枚举
- 迁移必须写 `downgrade()`，第一版允许空值
- 只改模型不改 Schema，接口会"收不到、返不出、更新丢"
