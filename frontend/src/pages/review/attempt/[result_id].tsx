"use client"
import { useContext, useEffect, useState, useMemo } from 'react'
import { useRouter } from 'next/router'
import { BookmarkIcon, BookOpenIcon } from '@heroicons/react/24/solid'
import AuthContext from '../../../contexts/AuthContext'
import { authFetch } from '../../../lib/authFetch'
import { Question } from '../../../lib/quizParser'
import { formatToBeijingTime } from '../../../lib/dateUtils'

// --- Component ---
export default function ReviewAttempt({ result_id: prop_result_id }: { result_id?: string }) {
  const router = useRouter()
  const { user } = useContext(AuthContext)
  const router_result_id = router.query.result_id as string;
  const result_id = prop_result_id || router_result_id;

  const [result, setResult] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showIncorrectOnly, setShowIncorrectOnly] = useState(false);
  const [bookmarks, setBookmarks] = useState<any[]>([]);
  const [savedVocab, setSavedVocab] = useState<Set<string>>(new Set());

  const bookmarkedQuestionIndexes = useMemo(() => {
    return new Set(bookmarks.map(b => b.question_index));
  }, [bookmarks]);

  // Fetch result data
  useEffect(() => {
    const fetchResultData = async () => {
      if (router.isReady && result_id) {
        setIsLoading(true);
        setError(null);
        try {
          const res = await authFetch(`/api/results/${result_id}`);
          if (!res.ok) throw new Error('Failed to fetch quiz result details.');
          const data = await res.json();
          if (!data.details || !Array.isArray(data.details.questions)) {
            throw new Error("Result data is corrupted or in an invalid format.");
          }
          setResult(data);
        } catch (err: any) {
          setError(err.message);
        } finally {
          setIsLoading(false);
        }
      }
    };
    fetchResultData();
  }, [router.isReady, result_id]);

  // Fetch bookmarks separately
  useEffect(() => {
    const fetchBookmarks = async () => {
      if (user && result_id) {
        try {
          // Fetch error question bookmarks
          const errorRes = await authFetch(`/api/bookmarks?username=${user.username}&type=error_question&result_id=${result_id}`);
          if (errorRes.ok) {
            setBookmarks(await errorRes.json());
          } else {
            console.error('Failed to fetch existing error bookmarks.');
            setBookmarks([]);
          }

          // Fetch all vocabulary bookmarks to check for existing words
          const vocabRes = await authFetch(`/api/bookmarks/list`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: user.username, type: 'vocabulary_word' })
          });
          if (vocabRes.ok) {
            const vocabData = await vocabRes.json();
            setSavedVocab(new Set(vocabData.map(v => v.word)));
          }

        } catch (err) {
          console.error('Error fetching bookmarks:', err);
        }
      }
    };

    fetchBookmarks();
  }, [user, result_id]);

  const handleBookmark = async (question: Question, questionIndex: number) => {
    if (!user || !result_id || !result?.quiz_id) {
        alert("Cannot bookmark: user or quiz context is missing.");
        return;
    }

    const existingBookmark = bookmarks.find(b => b.question_index === questionIndex);

    if (existingBookmark) {
      // --- Un-bookmark ---
      if (!confirm(`Are you sure you want to remove the bookmark for "${question.word}"?`)) return;
      try {
        const res = await authFetch(`/api/bookmarks/${existingBookmark._id}`, { method: 'DELETE' });
        if (!res.ok) throw new Error('Failed to remove bookmark.');
        setBookmarks(prev => prev.filter(b => b.question_index !== questionIndex));
        alert('Bookmark removed.');
      } catch (e) {
        console.error(e);
        alert((e as Error).message);
      }
    } else {
      // --- Create new bookmark ---
      const questionPayload = {
          username: user.username,
          type: 'error_question',
          quiz_id: result.quiz_id,
          result_id: result_id as string,
          question_index: questionIndex,
          user_answer: question.answer || '',
          word: question.word || '',
          question_prompt: question.sentence || `Sentence for "${question.word}"`,
          correct_answer: question.correctAnswer || null,
          ai_feedback: question.feedback || null,
      };

      try {
        const res = await authFetch('/api/bookmarks', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(questionPayload),
        });

        if (!res.ok) {
          const errData = await res.json();
          throw new Error(errData.error || 'Failed to bookmark question.');
        }

        const newBookmark = await res.json();
        setBookmarks(prev => [...prev, { ...questionPayload, _id: newBookmark.inserted_id }]);
        alert(`Question for '${question.word}' has been bookmarked!`);

      } catch (e) {
        console.error(e);
        alert((e as Error).message);
      }
    }
  };

  const handleSaveVocab = async (question: Question) => {
    if (!user || !question.word) {
      alert("Cannot save vocabulary: user or word is missing.");
      return;
    }

    // Frontend check to give instant feedback and prevent unnecessary API calls
    if (savedVocab.has(question.word)) {
      alert(`"${question.word}" is already in your vocabulary book.`);
      return;
    }

    let definition = question.definition;

    // If definition is missing, call AI
    if (!definition) {
      try {
        const aiRes = await authFetch('/api/ai/definition', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ word: question.word }),
        });
        if (!aiRes.ok) throw new Error('AI definition fetch failed.');
        const aiData = await aiRes.json();
        definition = aiData.definition;
      } catch (e) {
        alert(`Could not fetch AI definition for "${question.word}".`);
        console.error(e);
        return;
      }
    }

    // Save the word and definition
    try {
      const wordPayload = {
        username: user.username,
        type: 'vocabulary_word',
        word: question.word,
        definition: definition,
      };

      const res = await authFetch('/api/bookmarks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(wordPayload),
      });

      const resData = await res.json();

      if (res.ok) {
        setSavedVocab(prev => new Set(prev).add(question.word));
        alert(`"${question.word}" has been added to your vocabulary book.`);
      } else if (res.status === 409) {
        // Handle the case where the word already exists on the backend
        setSavedVocab(prev => new Set(prev).add(question.word)); // Sync frontend state
        alert(resData.error || `"${question.word}" is already in your vocabulary book.`);
      } else {
        // Handle other errors
        throw new Error(resData.error || 'Failed to save vocabulary word.');
      }

    } catch (e) {
      alert(`Failed to save "${question.word}" to vocabulary.`);
      console.error(e);
    }
  };

  const filteredQuestions = useMemo(() => {
    if (!result) return [];
    if (showIncorrectOnly) {
      return result.details.questions.filter(q => {
        if (q.type === 'sentence') return q.score !== undefined && q.score < 3;
        return !q.correct;
      });
    }
    return result.details.questions;
  }, [result, showIncorrectOnly]);

  if (isLoading) return <p className="p-6 text-center">Loading review...</p>;
  if (error) return <p className="p-6 text-center text-red-500">Error: {error}</p>;
  if (!result) return <p className="p-6 text-center">No result found.</p>;

  const { details, score, total_score, ts } = result;

  return (
    <main className="p-4 md:p-8 max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold text-gray-800 mb-2">{details.name || 'Quiz'} - Review</h1>
      <p className="text-sm text-gray-500 mb-4">Attempt from: {formatToBeijingTime(ts)}</p>

      <div className="my-6 p-4 bg-gray-100 rounded-lg text-center">
        <h2 className="text-xl font-semibold">Final Score</h2>
        <p className="text-4xl font-bold text-blue-600">{score} / {total_score}</p>
      </div>

      <>
        <div className="flex justify-end mb-4">
          <button
            onClick={() => setShowIncorrectOnly(!showIncorrectOnly)}
            className="px-4 py-2 text-sm font-medium text-white bg-gray-600 rounded-md hover:bg-gray-700"
          >
            {showIncorrectOnly ? 'Show All' : 'Show Incorrect Only'}
          </button>
        </div>

        <div className="space-y-4">
          {filteredQuestions.map((q, i) => {
            const isSentenceCorrect = q.type === 'sentence' && q.score !== undefined && q.score >= 3;
            const isCorrect = q.type === 'fill-in-the-blank' ? q.correct : isSentenceCorrect;
            const points = q.type === 'fill-in-the-blank' ? (q.correct ? 2 : 0) : q.score;

            return (
              <div key={i} className={`border-l-4 p-4 rounded-md ${isCorrect ? 'border-green-500 bg-green-50' : 'border-red-500 bg-red-50'}`}>
                <div className="flex justify-between items-start">
                  <p className="text-lg font-semibold text-gray-700">{(q.prompt || q.sentence)?.replace('___', `[${q.word}]`) || `Sentence for "${q.word}"`}</p>
                  <span className={`font-bold ${isCorrect ? 'text-green-600' : 'text-red-600'}`}>
                    {points !== undefined ? `${points} pts` : (isCorrect ? `2 pts` : '0 pts')}
                  </span>
                </div>
                <p className="mt-2">Your answer: <span className="font-mono p-1 bg-gray-200 rounded text-gray-800">{q.answer || 'No answer'}</span></p>

                {q.word && (
                  <div className="mt-3 flex items-center space-x-2">
                    <button
                      onClick={() => handleBookmark(q, i)}
                      className={`inline-flex items-center px-3 py-1 border border-transparent text-sm font-medium rounded-md shadow-sm text-white ${bookmarkedQuestionIndexes.has(i) ? 'bg-red-600 hover:bg-red-700' : 'bg-yellow-500 hover:bg-yellow-600'} focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-yellow-500`}
                    >
                      <BookmarkIcon className="h-4 w-4 mr-2" />
                      {bookmarkedQuestionIndexes.has(i) ? 'Bookmarked' : `Bookmark`}
                    </button>
                    <button
                      onClick={() => handleSaveVocab(q)}
                      disabled={savedVocab.has(q.word)}
                      className={`inline-flex items-center px-3 py-1 border border-transparent text-sm font-medium rounded-md shadow-sm text-white ${savedVocab.has(q.word) ? 'bg-green-600 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700'} focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500`}
                    >
                      <BookOpenIcon className="h-4 w-4 mr-2" />
                      {savedVocab.has(q.word) ? 'Vocab Saved' : 'Save Vocab'}
                    </button>
                  </div>
                )}

                {q.feedback && (
                  <div className="mt-2 text-sm text-blue-700 p-2 bg-blue-100 rounded">
                    <strong>AI Feedback:</strong> {q.feedback}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </>
    </main>
  )
}
