// Dev-only comparison data for DesignPreview.tsx. Deliberately duplicated from
// config/app.yaml's branding.palettes/branding.typography rather than fetched - Phase 2's brief
// requires "no backend calls" so this page works standalone, offline, with no auth, even if the
// API is down. THE SINGLE SOURCE OF TRUTH REMAINS config/app.yaml; if a palette or pairing
// changes there, update this file to match (a config.json fetch was deliberately rejected here -
// see docs/DESIGN.md's Design Preview section for the reasoning).
export type PaletteId = 'palette_1' | 'palette_2' | 'palette_3' | 'palette_4' | 'palette_5' | 'palette_6' | 'palette_7' | 'palette_8'
export type NeutralTrack = 'warm' | 'cool'

export type Palette = {
  id: PaletteId
  name: string
  colors: { primary: string; secondary: string; accent: string; background: string }
  buttonPrimaryBg: string
  usesButtonFallback: boolean // true when buttonPrimaryBg !== colors.primary (an AA contrast fallback, not a bug)
  neutralTrack: NeutralTrack
  logoColors: [string, string]
}

export const NEUTRAL_TRACKS: Record<NeutralTrack, Record<'900' | '700' | '500' | '300' | '200' | '100', string>> = {
  warm: { '900': '#1C1917', '700': '#44403C', '500': '#78716C', '300': '#D6D3D1', '200': '#E7E5E4', '100': '#F5F5F4' },
  cool: { '900': '#0F172A', '700': '#334155', '500': '#64748B', '300': '#CBD5E1', '200': '#E2E8F0', '100': '#F1F5F9' },
}

export const STATUS = {
  success: '#10B981', warning: '#F59E0B', error: '#EF4444',
  successText: '#047857', warningText: '#B45309', errorText: '#B91C1C',
  surface: '#FFFFFF',
}

export const PALETTES: Palette[] = [
  { id: 'palette_1', name: 'Academic Trust', colors: { primary: '#4F46E5', secondary: '#1E3A8A', accent: '#F59E0B', background: '#FAFAF9' }, buttonPrimaryBg: '#4F46E5', usesButtonFallback: false, neutralTrack: 'warm', logoColors: ['#4F46E5', '#F59E0B'] },
  { id: 'palette_2', name: 'Terracotta Scholar', colors: { primary: '#3B5BDB', secondary: '#1A2E5C', accent: '#E8590C', background: '#FDFBF7' }, buttonPrimaryBg: '#3B5BDB', usesButtonFallback: false, neutralTrack: 'warm', logoColors: ['#3B5BDB', '#E8590C'] },
  { id: 'palette_3', name: 'Forest Focus', colors: { primary: '#0F766E', secondary: '#134E4A', accent: '#65A30D', background: '#F7FDFB' }, buttonPrimaryBg: '#0F766E', usesButtonFallback: false, neutralTrack: 'cool', logoColors: ['#0F766E', '#65A30D'] },
  { id: 'palette_4', name: 'Midnight Study', colors: { primary: '#1E3A8A', secondary: '#0F172A', accent: '#38BDF8', background: '#F8FAFC' }, buttonPrimaryBg: '#1E3A8A', usesButtonFallback: false, neutralTrack: 'cool', logoColors: ['#1E3A8A', '#38BDF8'] },
  { id: 'palette_5', name: 'Coral Momentum', colors: { primary: '#2563EB', secondary: '#1E3A8A', accent: '#FB7185', background: '#FAFAFA' }, buttonPrimaryBg: '#2563EB', usesButtonFallback: false, neutralTrack: 'cool', logoColors: ['#2563EB', '#FB7185'] },
  { id: 'palette_6', name: 'Slate Professional', colors: { primary: '#3B82F6', secondary: '#334155', accent: '#8B5CF6', background: '#F9FAFB' }, buttonPrimaryBg: '#334155', usesButtonFallback: true, neutralTrack: 'cool', logoColors: ['#3B82F6', '#8B5CF6'] },
  { id: 'palette_7', name: 'Violet Insight', colors: { primary: '#6366F1', secondary: '#4C1D95', accent: '#22D3EE', background: '#FAFAFF' }, buttonPrimaryBg: '#4C1D95', usesButtonFallback: true, neutralTrack: 'cool', logoColors: ['#6366F1', '#22D3EE'] },
  { id: 'palette_8', name: 'Sunrise Clarity', colors: { primary: '#0EA5E9', secondary: '#0369A1', accent: '#FB923C', background: '#F0F9FF' }, buttonPrimaryBg: '#0369A1', usesButtonFallback: true, neutralTrack: 'cool', logoColors: ['#0EA5E9', '#FB923C'] },
]

export type TypographyPairing = { id: 'pairing_1' | 'pairing_2'; name: string; body: string; display: string; googleFontsUrl: string }

export const TYPOGRAPHY_PAIRINGS: TypographyPairing[] = [
  { id: 'pairing_1', name: 'Lexend + Space Grotesk (current default)', body: 'Lexend', display: 'Space Grotesk', googleFontsUrl: 'https://fonts.googleapis.com/css2?family=Lexend:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap' },
  { id: 'pairing_2', name: 'Karla + Fraunces (warmer, editorial contrast)', body: 'Karla', display: 'Fraunces', googleFontsUrl: 'https://fonts.googleapis.com/css2?family=Karla:wght@400;500;600;700&family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&display=swap' },
]
