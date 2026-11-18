<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Rated } from '../types'
import { angleOf, DIRECTIONS, type Direction, needle } from '../utils/compass'
import HintTip from './HintTip.vue'

// роза жанров: стрелка указывает на самую сильную сторону вкуса, закрашенная фигура – сила всех сторон сразу;
// пока оценок нет – стрелка медленно покачивается
const props = defineProps<{ ratings: Pick<Rated, 'rating' | 'genres'>[] }>()
const { t } = useI18n()
const state = computed(() => needle(props.ratings))
const C = 160
const RING = 128 // круг розы
const LABEL_R = 142 // подписи – снаружи круга, растут наружу: фигура вкуса их не задевает
const INNER = 26 // фигура вкуса: от этого радиуса (ноль) до SHAPE_R (самая сильная сторона)
const SHAPE_R = 108

function point(angle: number, r: number) {
  const a = (angle * Math.PI) / 180
  return { x: C + r * Math.sin(a), y: C - r * Math.cos(a) }
}

// подпись растёт наружу: справа – от левого края, слева – от правого, сверху и снизу – по центру
function anchor(angle: number) {
  const s = Math.sin((angle * Math.PI) / 180)
  return s > 0.1 ? 'start' : s < -0.1 ? 'end' : 'middle'
}

// сверху подпись поднимаем на высоту второй строки, снизу – опускаем, чтобы не лезла на круг
function labelY(d: Direction) {
  const c = Math.cos((angleOf(d) * Math.PI) / 180)
  const extra = lines(d).length - 1
  return point(angleOf(d), LABEL_R).y - (c > 0.5 ? extra * 12 : 0) + (c < -0.5 ? 4 : 0)
}

// название стороны – в одну или две строки (перенос задан в переводе); в тексте – через пробел
const lines = (d: Direction) => t(`dir.${d}`).split('\n')
const label = (d: Direction) => t(`dir.${d}`).replace('\n', ' ')

// фигура вкуса: радиус стороны – через корень из веса (площадь фигуры пропорциональна силе вкуса, без резких
// пиков), точки соединены гладкой замкнутой кривой Катмулла – Рома, переведённой в кривые Безье
const shape = computed(() => {
  const w = state.value.weights
  const max = Math.max(...DIRECTIONS.map((d) => w[d] ?? 0))
  if (max <= 0) return ''
  const pts = DIRECTIONS.map((d) => point(angleOf(d), INNER + (SHAPE_R - INNER) * Math.sqrt(Math.max(0, (w[d] ?? 0) / max))))
  const n = pts.length
  const at = (i: number) => pts[(i + n) % n]
  const f = (x: number) => x.toFixed(1)
  let path = `M${f(pts[0].x)} ${f(pts[0].y)}`
  for (let i = 0; i < n; i++) {
    const [p0, p1, p2, p3] = [at(i - 1), at(i), at(i + 1), at(i + 2)]
    const c1 = { x: p1.x + (p2.x - p0.x) / 6, y: p1.y + (p2.y - p0.y) / 6 }
    const c2 = { x: p2.x - (p3.x - p1.x) / 6, y: p2.y - (p3.y - p1.y) / 6 }
    path += ` C${f(c1.x)} ${f(c1.y)} ${f(c2.x)} ${f(c2.y)} ${f(p2.x)} ${f(p2.y)}`
  }
  return `${path} Z`
})
const caption = computed(() =>
  state.value.top ? t('hero.compassTop', { dir: label(state.value.top) }) : t('hero.compassEmpty'),
)
</script>

<template>
  <figure class="relative mx-auto w-full max-w-[560px]">
    <!-- поле шире круга ровно на длину подписей (самая длинная – казахская «және отбасылық») -->
    <svg viewBox="-100 -20 520 358" role="img" :aria-label="caption">
      <circle :cx="C" :cy="C" :r="RING" fill="var(--surface)" stroke="var(--border)" />
      <circle :cx="C" :cy="C" :r="SHAPE_R" fill="none" stroke="var(--border)" stroke-dasharray="2 6" />
      <circle :cx="C" :cy="C" :r="(INNER + SHAPE_R) / 2" fill="none" stroke="var(--border)" stroke-dasharray="2 6" opacity="0.6" />
      <path
        v-if="shape"
        :d="shape"
        fill="var(--accent)"
        fill-opacity="0.16"
        stroke="var(--accent)"
        stroke-opacity="0.7"
        stroke-width="1.5"
        stroke-linejoin="round"
        class="shape"
      />
      <g v-for="d in DIRECTIONS" :key="d">
        <line
          :x1="point(angleOf(d), RING - 12).x"
          :y1="point(angleOf(d), RING - 12).y"
          :x2="point(angleOf(d), RING).x"
          :y2="point(angleOf(d), RING).y"
          :stroke="state.top === d ? 'var(--accent)' : 'var(--muted)'"
          stroke-width="2"
          stroke-linecap="round"
        />
        <text
          :x="point(angleOf(d), LABEL_R).x"
          :y="labelY(d)"
          :text-anchor="anchor(angleOf(d))"
          dominant-baseline="middle"
          font-size="12"
          :font-weight="state.top === d ? 700 : 500"
          :fill="state.top === d ? 'var(--accent)' : 'var(--muted)'"
        >
          <tspan
            v-for="(line, i) in lines(d)"
            :key="i"
            :x="point(angleOf(d), LABEL_R).x"
            :dy="i === 0 ? `${-(lines(d).length - 1) * 0.55 * (Math.abs(Math.cos((angleOf(d) * Math.PI) / 180)) > 0.5 ? 0 : 1)}em` : '1.1em'"
          >
            {{ line }}
          </tspan>
        </text>
      </g>
      <g class="needle" :class="{ idle: state.strength === 0 }" :style="{ transform: `rotate(${state.angle}deg)` }">
        <path :d="`M${C} ${C - 50 - 40 * state.strength} L${C + 9} ${C} L${C - 9} ${C} Z`" fill="var(--accent)" />
        <path :d="`M${C} ${C + 46} L${C + 9} ${C} L${C - 9} ${C} Z`" fill="var(--muted)" opacity="0.6" />
      </g>
      <circle :cx="C" :cy="C" r="7" fill="var(--bg)" stroke="var(--accent)" stroke-width="2" />
    </svg>
    <figcaption class="mt-2 text-center text-sm text-muted">
      {{ caption }}
      <HintTip :text="t('hint.compass')" />
    </figcaption>
  </figure>
</template>

<style scoped>
.needle {
  transform-origin: 160px 160px;
  transition: transform 0.9s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.needle.idle {
  animation: sway 4s ease-in-out infinite;
}
.shape {
  transition: all 0.6s ease;
}
@keyframes sway {
  0%,
  100% {
    transform: rotate(-14deg);
  }
  50% {
    transform: rotate(14deg);
  }
}
</style>
