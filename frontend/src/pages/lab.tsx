import React, { useState, useEffect } from 'react';
import { BeakerIcon, LockClosedIcon } from '@heroicons/react/24/outline';

const LabPage = () => {
  const [accessKey, setAccessKey] = useState('');
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [error, setError] = useState('');

  const labAccessKey = process.env.NEXT_PUBLIC_LAB_ACCESS_KEY;

  useEffect(() => {
    // Check session storage to maintain access after refresh
    if (sessionStorage.getItem('lab_access_granted') === 'true') {
      setIsAuthenticated(true);
    }
  }, []);

  const handleAccess = () => {
    if (accessKey === labAccessKey) {
      setIsAuthenticated(true);
      setError('');
      sessionStorage.setItem('lab_access_granted', 'true');
    } else {
      setError('Invalid access key.');
      setIsAuthenticated(false);
      sessionStorage.removeItem('lab_access_granted');
    }
  };

  return (
    <main className="min-h-screen bg-gray-100 flex flex-col items-center justify-center p-4">
      <div className="w-full max-w-2xl mx-auto">
        <div className="text-center mb-8">
          <BeakerIcon className="mx-auto h-12 w-12 text-purple-600" />
          <h1 className="mt-4 text-4xl font-extrabold text-gray-900">
            Experimental Lab
          </h1>
          <p className="mt-2 text-lg text-gray-600">
            This area contains experimental features. Proceed with caution.
          </p>
        </div>

        {!isAuthenticated ? (
          <div className="bg-white p-8 rounded-lg shadow-md">
            <div className="flex items-center mb-4">
              <LockClosedIcon className="h-6 w-6 text-gray-500 mr-3" />
              <h2 className="text-2xl font-bold text-gray-800">Access Required</h2>
            </div>
            <p className="text-gray-600 mb-6">
              Please enter the developer access key to continue.
            </p>
            <div className="flex gap-4">
              <input
                type="password"
                value={accessKey}
                onChange={(e) => setAccessKey(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleAccess()}
                className="flex-grow border p-3 rounded-lg focus:ring-2 focus:ring-purple-500 focus:outline-none"
                placeholder="Enter access key..."
              />
              <button
                onClick={handleAccess}
                className="bg-purple-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-purple-700 transition-colors"
              >
                Unlock
              </button>
            </div>
            {error && <p className="text-red-500 mt-4 text-center">{error}</p>}
          </div>
        ) : (
          <div className="bg-white p-8 rounded-lg shadow-md animate-fade-in">
            <h2 className="text-2xl font-bold text-gray-800 mb-6">Test Features</h2>
            <div className="space-y-4">
              {/* --- Add your experimental components or features here --- */}
              <div className="p-4 border rounded-lg bg-gray-50">
                <h3 className="font-semibold">Feature 1: Experimental Button</h3>
                <p className="text-sm text-gray-600">This is a placeholder for a new feature.</p>
                <button className="mt-2 bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600">
                  Run Test
                </button>
              </div>
              <div className="p-4 border rounded-lg bg-gray-50">
                <h3 className="font-semibold">Feature 2: Another Test Area</h3>
                <p className="text-sm text-gray-600">More experimental content can go here.</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  );
};

export default LabPage;
