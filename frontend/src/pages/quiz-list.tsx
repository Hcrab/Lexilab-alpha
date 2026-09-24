"use client"
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { StarIcon, ClockIcon, CalendarDaysIcon } from '@heroicons/react/24/solid'
import { formatToBeijingTime } from '../lib/dateUtils'
import withAuth from '../components/withAuth'

interface Quiz {
  _id: string; // Keep original _id from MongoDB
  id: string;
  name: string;
  type: string;
  created_at: string;
}

function QuizList() {
  const [todayQuiz, setTodayQuiz] = useState<Quiz | null>(null);
  const [pastQuizzes, setPastQuizzes] = useState<Quiz[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchQuizzes = async () => {
      setIsLoading(true);
      setError(null);
      try {
        // Fetch today's quiz and the full list in parallel
        const [todayRes, listRes] = await Promise.all([
          fetch('/api/quizzes/today'),
          fetch('/api/quizzes?per_page=9999')
        ]);

        if (!listRes.ok) throw new Error('Failed to fetch the quiz list.');

        const todayData = todayRes.ok ? await todayRes.json() : null;
        const listResponse = await listRes.json();
        const listData: Quiz[] = listResponse.quizzes || [];

        // Map _id to id for frontend consistency
        const mappedListData = listData.map(q => ({ ...q, id: q._id }));
        const mappedTodayData = todayData ? { ...todayData, id: todayData._id } : null;

        setTodayQuiz(mappedTodayData);

        // Filter out today's quiz from the main list to create the "past quizzes" list
        const past = mappedListData.filter(q => q.id !== mappedTodayData?.id);
        setPastQuizzes(past);

      } catch (err) {
        setError((err as Error).message);
        setPastQuizzes([]); // Ensure state is an array on error
      } finally {
        setIsLoading(false);
      }
    };

    fetchQuizzes();
  }, []);

  const renderQuizCard = (quiz: Quiz, isToday: boolean = false) => (
    <li key={quiz.id} className={`border rounded-lg shadow-sm hover:shadow-lg transition-shadow duration-200 ${isToday ? 'bg-gradient-to-r from-blue-50 to-indigo-50 border-blue-200' : 'bg-white'}`}>
      <Link href={`/quiz/${quiz.id}`} className="block p-5">
        <div className="flex justify-between items-start">
          <p className="font-bold text-lg text-gray-800">{quiz.name}</p>
          {isToday && <StarIcon className="h-6 w-6 text-yellow-400" />}
        </div>
        <div className="flex items-center text-sm text-gray-500 mt-3">
          <ClockIcon className="h-4 w-4 mr-1.5" />
          <span>Created: {formatToBeijingTime(quiz.created_at)}</span>
        </div>
      </Link>
    </li>
  );

  if (isLoading) return <p className="p-8 text-center text-gray-600">Loading quizzes...</p>;
  if (error) return <p className="p-8 text-center text-red-600 font-semibold">Error: {error}</p>;

  return (
    <main className="p-4 md:p-8 max-w-4xl mx-auto">
      <h1 className="text-4xl font-extrabold text-gray-800 mb-8 tracking-tight">Quiz Library</h1>

      {/* Today's Quiz Section */}
      <section className="mb-10">
        <div className="flex items-center mb-4">
          <CalendarDaysIcon className="h-7 w-7 text-blue-600 mr-3"/>
          <h2 className="text-2xl font-bold text-gray-700">Today's Quiz</h2>
        </div>
        {todayQuiz ? (
          <ul className="space-y-3">
            {renderQuizCard(todayQuiz, true)}
          </ul>
        ) : (
          <div className="text-center py-6 px-4 bg-gray-50 rounded-lg">
            <p className="text-gray-500">No quiz available for today.</p>
          </div>
        )}
      </section>

      {/* Past Quizzes Section */}
      <section>
        <h2 className="text-2xl font-bold text-gray-700 mb-4 border-t pt-6">Past Quizzes</h2>
        {pastQuizzes.length > 0 ? (
          <ul className="space-y-4">
            {pastQuizzes.map(quiz => renderQuizCard(quiz))}
          </ul>
        ) : (
          <div className="text-center py-6 px-4 bg-gray-50 rounded-lg">
            <p className="text-gray-500">There are no past quizzes to show.</p>
          </div>
        )}
      </section>
    </main>
  );
}

export default withAuth(QuizList)