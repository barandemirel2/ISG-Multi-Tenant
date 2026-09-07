import React from "react";
import { useTheme } from "@/context/ThemeContext";
import { Moon, Sun, Monitor } from "lucide-react";
import { motion } from "framer-motion";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();

  const options = [
    { id: "dark", label: "Karanlık Tema", icon: Moon, color: "text-amber-400" },
    { id: "light", label: "Aydınlık Tema", icon: Sun, color: "text-amber-500" },
    { id: "system", label: "Sistem Teması", icon: Monitor, color: "text-blue-400" },
  ];

  return (
    <div className="inline-flex items-center p-1 rounded-control surface-card text-xs font-sans">
      {options.map((opt) => {
        const Icon = opt.icon;
        const isSelected = theme === opt.id;
        return (
          <button
            key={opt.id}
            type="button"
            onClick={() => setTheme(opt.id)}
            title={opt.label}
            data-testid={`theme-toggle-${opt.id}`}
            className={`relative p-2 rounded-control transition-colors duration-micro ease-firm cursor-pointer active:scale-95 flex items-center justify-center ${
              isSelected
                ? "text-ink-primary"
                : "text-ink-tertiary hover:text-ink-primary"
            }`}
          >
            {isSelected && (
              <motion.div
                layoutId="active-theme-pill"
                className="absolute inset-0 bg-surface-card-2 rounded-control shadow-card border border-border-strong z-0"
                transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
              />
            )}
            <Icon className={`w-4 h-4 relative z-10 ${opt.color}`} />
          </button>
        );
      })}
    </div>
  );
}

export default ThemeToggle;
