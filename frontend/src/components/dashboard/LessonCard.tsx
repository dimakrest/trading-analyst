import { Lock, Play, CheckCircle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';

type LessonStatus = 'locked' | 'active' | 'complete';

interface LessonCardProps {
  lessonNumber: number;
  title: string;
  description: string;
  status: LessonStatus;
  onStart?: () => void;
}

export default function LessonCard({ lessonNumber, title, description, status, onStart }: LessonCardProps) {
  const isLocked = status === 'locked';
  const isActive = status === 'active';
  const isComplete = status === 'complete';

  return (
    <Card
      data-testid={`lesson-card-${lessonNumber}`}
      className={`border transition-colors ${
        isActive
          ? 'bg-zinc-900 border-blue-500'
          : isComplete
          ? 'bg-zinc-900 border-zinc-700 opacity-75'
          : 'bg-zinc-900 border-zinc-800 opacity-60'
      }`}
    >
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <Badge variant="outline" className="text-zinc-400 border-zinc-600 text-xs">
            Lesson {lessonNumber}
          </Badge>
          {isLocked && <Lock className="h-4 w-4 text-zinc-600" />}
          {isActive && <Play className="h-4 w-4 text-blue-400" />}
          {isComplete && <CheckCircle className="h-4 w-4 text-green-500" />}
        </div>
        <CardTitle className={`text-base ${isLocked ? 'text-zinc-500' : 'text-white'}`}>
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className={`text-sm mb-3 ${isLocked ? 'text-zinc-600' : 'text-zinc-400'}`}>
          {description}
        </p>
        {isActive && (
          <Button
            size="sm"
            onClick={onStart}
            className="bg-blue-600 hover:bg-blue-700 text-white"
          >
            Start Lesson
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
