import { CHART_COLOR_CLASSES } from '../../../constants/chartColors';

interface ChartLegendProps {
  className?: string;
}

/**
 * Color legend for stock chart explaining visual elements
 */
export const ChartLegend = ({ className = '' }: ChartLegendProps) => {
  return (
    <div
      className={`flex flex-wrap items-center gap-4 text-xs ${className}`}
      role="list"
      aria-label="Chart color legend"
    >
      <div className="flex items-center gap-1.5" role="listitem">
        <div className={`w-3 h-3 ${CHART_COLOR_CLASSES.BULLISH} rounded-sm`} aria-hidden="true" />
        <span className="text-gray-600">Bullish</span>
      </div>

      <div className="flex items-center gap-1.5" role="listitem">
        <div className={`w-3 h-3 ${CHART_COLOR_CLASSES.BEARISH} rounded-sm`} aria-hidden="true" />
        <span className="text-gray-600">Bearish</span>
      </div>

      <div className="flex items-center gap-1.5" role="listitem">
        <div className={`w-3 h-0.5 ${CHART_COLOR_CLASSES.MA_20}`} aria-hidden="true" />
        <span className="text-gray-600">MA 20</span>
      </div>

      <div className="flex items-center gap-1.5" role="listitem">
        <div className={`w-3 h-0.5 ${CHART_COLOR_CLASSES.WICKS}`} aria-hidden="true" />
        <span className="text-gray-600">Wicks</span>
      </div>

      <div className="flex items-center gap-1.5" role="listitem">
        <div className={`w-3 h-0.5 ${CHART_COLOR_CLASSES.CCI}`} aria-hidden="true" />
        <span className="text-gray-600">CCI</span>
      </div>
    </div>
  );
};
