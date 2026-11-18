<template>
  <!-- стрелка компаса: янтарный конец – «куда смотреть», серый – обратный -->
  <svg viewBox="0 0 32 32" aria-hidden="true">
    <circle cx="16" cy="16" r="14" fill="none" stroke="var(--accent)" stroke-width="2" />
    <path d="M16 5 L19.5 16 L16 27 L12.5 16 Z" fill="var(--accent)" />
    <path d="M16 16 L19.5 16 L16 27 L12.5 16 Z" fill="var(--muted)" />
    <circle cx="16" cy="16" r="2" fill="var(--bg)" />
  </svg>
</template>
