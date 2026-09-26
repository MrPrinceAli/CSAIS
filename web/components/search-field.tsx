"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Kolom pencarian yang "mengetik" contoh kata kunci sebagai placeholder,
 * berhenti saat difokus atau sudah berisi. Tanpa gerak: placeholder biasa.
 */
export function SearchField({
  id,
  name,
  defaultValue = "",
  examples,
  placeholder,
  className = "",
  type = "search",
}: {
  id: string;
  name: string;
  defaultValue?: string;
  examples: string[];
  placeholder: string;
  className?: string;
  type?: string;
}) {
  const [text, setText] = useState(placeholder);
  const active = useRef(!defaultValue);

  useEffect(() => {
    if (!examples.length || defaultValue) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let i = 0;
    let pos = 0;
    let deleting = false;
    let timer = 0;
    const step = () => {
      if (!active.current) {
        timer = window.setTimeout(step, 600);
        return;
      }
      const word = examples[i % examples.length];
      if (!deleting) {
        pos += 1;
        setText(`${word.slice(0, pos)}▌`);
        if (pos >= word.length) {
          deleting = true;
          timer = window.setTimeout(step, 1500);
          return;
        }
        timer = window.setTimeout(step, 55 + Math.random() * 45);
      } else {
        pos -= 1;
        setText(`${word.slice(0, pos)}▌`);
        if (pos <= 0) {
          deleting = false;
          i += 1;
          timer = window.setTimeout(step, 350);
          return;
        }
        timer = window.setTimeout(step, 28);
      }
    };
    timer = window.setTimeout(step, 900);
    return () => clearTimeout(timer);
  }, [examples, defaultValue]);

  return (
    <input
      id={id}
      name={name}
      type={type}
      defaultValue={defaultValue}
      placeholder={text}
      className={className}
      onFocus={() => {
        active.current = false;
        setText(placeholder);
      }}
      onBlur={(e) => {
        active.current = !e.currentTarget.value;
      }}
      onChange={(e) => {
        active.current = !e.currentTarget.value;
      }}
    />
  );
}
