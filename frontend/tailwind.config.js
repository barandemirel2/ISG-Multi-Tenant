/** @type {import('tailwindcss').Config} */
module.exports = {
    darkMode: ["class"],
    content: [
    "./src/**/*.{js,jsx,ts,tsx}",
    "./public/index.html"
  ],
  theme: {
    extend: {
      borderRadius: {
        // ─── Preserved legacy mapping (do NOT change without migration sweep) ─
        // Master prompt §2: cards=12px, controls=8px. shadcn `--radius: 0.75rem`
        // (12px) was historically bound to `lg`. Keep `lg` at 12px so existing
        // components don't silently shrink. New code should use `rounded-card`
        // (12px) and `rounded-control` (8px) explicitly.
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
        // ─── v1 design-tokens.json — explicit semantic names ───────────
        card:    'var(--radius-card)',     /* 12px — surfaces */
        control: 'var(--radius-control)',  /*  8px — inputs, buttons */
        pill:    'var(--radius-pill)',     /*  9999px */
        xs:      'var(--radius-xs)'        /*  4px — chips, badges */
      },
      colors: {
        // ─── Existing shadcn HSL bridge (kept for backward compatibility) ─
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))'
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))'
        },
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))'
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))'
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))'
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))'
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))'
        },
        // ─── border: HSL bridge (shadcn compat) + design-system aware
        //       semantic names. DEFAULT preserves the legacy `border-border`
        //       shadcn usage; `default`/`strong`/`focus` expose canonical
        //       tokens.css --border-* variables so they can be used as
        //       `border-border-{default|strong|focus}` without breaking
        //       the HSL bridge.
        border: {
          DEFAULT:    'hsl(var(--border))',
          'default':  'var(--border-default)',
          strong:     'var(--border-strong)',
          focus:      'var(--border-focus)'
        },
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        chart: {
          '1': 'hsl(var(--chart-1))',
          '2': 'hsl(var(--chart-2))',
          '3': 'hsl(var(--chart-3))',
          '4': 'hsl(var(--chart-4))',
          '5': 'hsl(var(--chart-5))'
        },
        // ─── v1 design-tokens.json (Sanzo harmonies) ────────────────────
        // Use these in NEW components. Pre-existing HSL bridge is preserved
        // for components that haven't migrated yet. Master prompt: stock
        // Tailwind red-600 / amber-500 / emerald-600 are BANNED for risk.
        surface: {
          page:     'var(--surface-page)',
          'page-2': 'var(--surface-page-2)',
          card:     'var(--surface-card)',
          'card-2': 'var(--surface-card-2)',
          overlay:  'var(--surface-overlay)'
        },
        ink: {
          DEFAULT:  'var(--ink-primary)',
          primary:  'var(--ink-primary)',
          secondary:'var(--ink-secondary)',
          tertiary: 'var(--ink-tertiary)',
          inverse:  'var(--ink-inverse)'
        },
        risk: {
          critical:  'var(--risk-critical)',
          'critical-2':'var(--risk-critical-2)',
          'critical-bg':'var(--risk-critical-bg)',
          'critical-border':'var(--risk-critical-border)',
          moderate:  'var(--risk-moderate)',
          'moderate-2':'var(--risk-moderate-2)',
          'moderate-bg':'var(--risk-moderate-bg)',
          'moderate-border':'var(--risk-moderate-border)',
          compliant: 'var(--risk-compliant)',
          'compliant-2':'var(--risk-compliant-2)',
          'compliant-bg':'var(--risk-compliant-bg)',
          'compliant-border':'var(--risk-compliant-border)',
          info:      'var(--risk-info)',
          'info-bg': 'var(--risk-info-bg)'
        },
        // ─── v1.1 design-tokens.json — neutral primary ACTION namespace
        //       For routine primary CTAs (login submit, save). NOT for risk
        //       semantics. All keys aliased to ink.* so the dark/light mode
        //       inversion happens via tokens.css (no new hex values).
        action: {
          DEFAULT:                'var(--action-primary)',
          primary:                'var(--action-primary)',
          'primary-hover':        'var(--action-primary-hover)',
          'primary-foreground':   'var(--action-primary-foreground)'
        }
      },
      // ─── v1 design-tokens.json — motion extensions ────────────────────
      transitionDuration: {
        micro:    '200ms',
        standard: '350ms',
        entrance: '500ms'
      },
      transitionTimingFunction: {
        swift: 'cubic-bezier(0.16, 1, 0.3, 1)',
        firm:  'cubic-bezier(0.4, 0, 0.2, 1)'
      },
      keyframes: {
        'accordion-down': {
          from: {
            height: '0'
          },
          to: {
            height: 'var(--radix-accordion-content-height)'
          }
        },
        'accordion-up': {
          from: {
            height: 'var(--radix-accordion-content-height)'
          },
          to: {
            height: '0'
          }
        }
      },
      animation: {
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up': 'accordion-up 0.2s ease-out'
      }
    }
  },
  plugins: [require("tailwindcss-animate")],
};