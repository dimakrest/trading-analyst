import { useEffect, useState } from 'react';
import { Card, CardHeader, CardTitle } from '../ui/card';
import LessonCard from './LessonCard';

type LessonStatus = 'locked' | 'active' | 'complete';
type Progress = { lessons: Record<string, LessonStatus> };

const LESSON_METADATA = [
  { number: 0, title: 'Getting Started', description: 'Set up your environment and meet your AI coding partner' },
  { number: 1, title: 'Your First Chart', description: 'Build a candlestick chart with real stock data' },
  { number: 2, title: 'Technical Indicators', description: 'Add moving averages and RSI to your chart' },
  { number: 3, title: 'Stock Search', description: 'Build a live stock search with autocomplete' },
  { number: 4, title: 'Watchlist', description: 'Create a personal watchlist with persistence' },
  { number: 5, title: 'Screening', description: 'Build a stock screener with multiple filters' },
  { number: 6, title: 'Live Analysis', description: 'Run automated analysis on your watchlist stocks' },
];

export default function ProgressDashboard() {
  const [progress, setProgress] = useState<Progress>({ lessons: {} });

  useEffect(() => {
    fetch('/progress.json')
      .then((r) => r.json())
      .then(setProgress)
      .catch(() => {
        /* use default empty progress */
      });
  }, []);

  return (
    <div data-testid="progress-dashboard" className="p-6 max-w-4xl mx-auto">
      <Card className="bg-zinc-900 border-zinc-800 mb-6">
        <CardHeader>
          <CardTitle className="text-white text-2xl">Trading Analyst Course</CardTitle>
          <p className="text-zinc-400">Build a professional stock analysis tool with Claude Code</p>
        </CardHeader>
      </Card>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {LESSON_METADATA.map((lesson) => (
          <LessonCard
            key={lesson.number}
            lessonNumber={lesson.number}
            title={lesson.title}
            description={lesson.description}
            status={progress.lessons[String(lesson.number)] ?? 'locked'}
          />
        ))}
      </div>
    </div>
  );
}
