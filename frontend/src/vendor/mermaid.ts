import type Mermaid from 'mermaid'
import { MERMAID_ASSET_DIR } from './mermaidAssetPath'

export type MermaidApi = typeof Mermaid

let loadPromise: Promise<MermaidApi> | null = null

export function loadMermaid(): Promise<MermaidApi> {
  if (loadPromise) return loadPromise

  const baseUrl = new URL(import.meta.env.BASE_URL, window.location.href)
  const entryUrl = new URL(`${MERMAID_ASSET_DIR}/mermaid.esm.min.mjs`, baseUrl).href
  loadPromise = import(/* @vite-ignore */ entryUrl)
    .then((module) => module.default as MermaidApi)
    .catch((error) => {
      loadPromise = null
      throw error
    })

  return loadPromise
}

let rendererPromise: Promise<MermaidApi> | null = null

/**
 * The single mermaid instance for every diagram surface in the app. The
 * neutral theme and strict security level are part of the app's diagram
 * contract, so they are configured once here instead of per consumer.
 */
export function getMermaidRenderer(): Promise<MermaidApi> {
  if (!rendererPromise) {
    rendererPromise = loadMermaid()
      .then((mermaid) => {
        mermaid.initialize({
          startOnLoad: false,
          theme: 'neutral',
          securityLevel: 'strict',
          flowchart: {
            useMaxWidth: true,
            htmlLabels: true,
          },
        })
        return mermaid
      })
      .catch((error) => {
        rendererPromise = null
        throw error
      })
  }
  return rendererPromise
}
