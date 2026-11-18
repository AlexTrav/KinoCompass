import { BarChart, LineChart, ScatterChart } from 'echarts/charts'
import { DataZoomComponent, GridComponent, LegendComponent, MarkLineComponent, TooltipComponent } from 'echarts/components'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { computed } from 'vue'
import { useTheme } from './composables/useTheme'
import type { Direction } from './utils/compass'

// только нужные части ECharts: графики грузятся отдельным куском вместе со страницами, где они есть
use([BarChart, LineChart, ScatterChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent,
  MarkLineComponent, CanvasRenderer])

// восемь сторон компаса – восемь цветов проверенной категориальной палитры (порядок слотов фиксирован,
// для тёмной темы – те же оттенки, подобранные под тёмный фон); цвет никогда не единственный признак –
// у каждого графика есть подписи или легенда
const LIGHT = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948']
const DARK = ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#008300', '#9085e9', '#e66767']
export const DIRECTION_ORDER: Direction[] = ['action', 'scifi', 'animation', 'comedy', 'romance', 'drama', 'thriller', 'horror']

export function useChartColors() {
  const { theme } = useTheme()
  return computed(() => {
    const dark = theme.value === 'dark'
    return {
      dark,
      series: dark ? DARK : LIGHT,
      text: dark ? '#f1ede6' : '#1f1b16',
      muted: dark ? '#a39caf' : '#6b6257',
      line: dark ? '#2e2b37' : '#ddd5c8',
      surface: dark ? '#17161d' : '#ffffff',
      accent: dark ? '#f0a83a' : '#a85f00',
      other: dark ? '#5d5868' : '#b5ab9c',
    }
  })
}

// общий вид подсказки и осей: текст – цветами текста, сетка – едва заметная
export function baseOptions(c: ReturnType<typeof useChartColors>['value']) {
  return {
    textStyle: { fontFamily: 'Onest Variable, system-ui, sans-serif', color: c.text },
    tooltip: {
      backgroundColor: c.surface,
      borderColor: c.line,
      textStyle: { color: c.text },
      extraCssText: 'border-radius:10px;box-shadow:0 6px 24px rgba(0,0,0,.25);',
    },
    axis: {
      axisLine: { lineStyle: { color: c.line } },
      axisTick: { show: false },
      axisLabel: { color: c.muted },
      splitLine: { lineStyle: { color: c.line, opacity: 0.5 } },
    },
  }
}
