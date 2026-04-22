"use client";

import { useState } from "react";
import { Eye, EyeOff, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface AuthFieldProps {
  label: string;
  type?: "email" | "text" | "password";
  value: string;
  onChange: (value: string) => void;
  error?: boolean;
  disabled?: boolean;
  icon: LucideIcon;
  placeholder?: string;
  autoComplete?: string;
}

export function AuthField({
  label,
  type = "text",
  value,
  onChange,
  error,
  disabled,
  icon: Icon,
  placeholder,
  autoComplete,
}: AuthFieldProps) {
  const [focused, setFocused] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const isPassword = type === "password";
  const inputType = isPassword ? (showPassword ? "text" : "password") : type;

  const borderStyle = error
    ? { border: "1.5px solid #F87171" }
    : focused
      ? { border: "1.5px solid #4ADE80", boxShadow: "0 0 0 3px rgba(74,222,128,0.1), inset 0 0 20px rgba(74,222,128,0.03)" }
      : { border: "1.5px solid rgba(74,222,128,0.15)" };

  return (
    <div className="flex flex-col gap-[6px]">
      <label
        className={cn(
          "font-mono text-[10px] font-medium uppercase tracking-[0.1em] transition-colors duration-200",
          error ? "text-[#F87171]" : focused ? "text-brand-green" : "text-subtext",
        )}
      >
        {label}
      </label>
      <div
        className={cn(
          "flex items-center gap-2 rounded-input px-[14px] bg-black/40 transition-all duration-200",
          disabled && "opacity-50",
        )}
        style={borderStyle}
      >
        <Icon size={15} className="text-subtext shrink-0" />
        <input
          type={inputType}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          disabled={disabled}
          placeholder={placeholder}
          autoComplete={autoComplete}
          className="flex-1 bg-transparent py-[14px] text-sm font-sans text-foreground outline-none placeholder:text-subtext/60"
        />
        {isPassword && (
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            disabled={disabled}
            className="text-subtext hover:text-foreground transition-colors"
            tabIndex={-1}
          >
            {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
          </button>
        )}
      </div>
    </div>
  );
}
