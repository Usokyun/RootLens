import 'vue-router'

declare module 'vue-router' {
  interface RouteMeta {
    label: string
    description: string
  }
}
