import { FormEvent, useState } from 'react';
import { searchFaces, MatchResult } from './api';
import ResultsGrid from './components/ResultsGrid';

function App() {
  const [queryFile, setQueryFile] = useState<File | null>(null);
  const [queryPreview, setQueryPreview] = useState<string | null>(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [matches, setMatches] = useState<MatchResult[]>([]);
  const [queryFaces, setQueryFaces] = useState(0);
  const [reportUrl, setReportUrl] = useState<string | null>(null);

  const readPreview = (file: File) => {
    const reader = new FileReader();
    reader.onloadend = () => setQueryPreview(reader.result as string);
    reader.readAsDataURL(file);
  };

  const resetFeedback = () => {
    setStatusMessage(null);
    setErrorMessage(null);
  };

  const handleSearch = async (event: FormEvent) => {
    event.preventDefault();
    if (!queryFile) {
      setErrorMessage('Please select a face to search.');
      return;
    }
    resetFeedback();
    setSearchLoading(true);
    try {
      const response = await searchFaces(queryFile);
      setMatches(response.matches);
      setQueryFaces(response.query_faces);
      setReportUrl(response.report_url ?? null);
      setStatusMessage(
        response.matches.length
          ? `Found ${response.matches.length} matching photo${response.matches.length !== 1 ? 's' : ''}.`
          : 'No matches yet. Try another photo or expand your dataset.',
      );
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Search failed.');
      setMatches([]);
      setQueryFaces(0);
      setReportUrl(null);
    } finally {
      setSearchLoading(false);
    }
  };

  const handleFileChange = (file: File | null) => {
    setQueryFile(file);
    if (file) {
      readPreview(file);
    } else {
      setQueryPreview(null);
    }
  };

  return (
    <div className="page">
      <header className="hero">
        <p className="eyebrow">Face Intelligence Toolkit</p>
        <h1>Drop a portrait. Retrieve every appearance.</h1>
        <p className="subtitle">
          The backend watches your dataset folder, encodes every face, and the search panel below instantly surfaces
          where that person shows up.
        </p>
      </header>

      <section className="scanner-card">
        <form onSubmit={handleSearch}>
          <label htmlFor="query-file" className="dropzone">
            <input
              id="query-file"
              type="file"
              accept="image/*"
              onChange={(event) => handleFileChange(event.target.files?.[0] ?? null)}
            />
            {queryPreview ? (
              <img src={queryPreview} alt="Query preview" />
            ) : (
              <div className="placeholder">
                <span>Click to upload</span>
                <p>or drag an image of a single face</p>
              </div>
            )}
          </label>
          <button type="submit" disabled={searchLoading}>
            {searchLoading ? 'Scanning library…' : 'Find this person'}
          </button>
        </form>

        <div className="tips">
          <p>Tips</p>
          <ul>
            <li>Use a clear, front-facing portrait for best results.</li>
            <li>Make sure your dataset folder is configured in the backend `.env`.</li>
            <li>Matches are sorted by confidence (lower embedding distance).</li>
          </ul>
        </div>
      </section>

      {statusMessage && <div className="status success">{statusMessage}</div>}
      {errorMessage && <div className="status error">{errorMessage}</div>}

      <ResultsGrid matches={matches} queryFaces={queryFaces} loading={searchLoading} reportUrl={reportUrl} />
    </div>
  );
}

export default App;
