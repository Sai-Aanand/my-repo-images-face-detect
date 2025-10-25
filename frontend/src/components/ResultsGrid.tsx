import { MatchResult } from '../api';

interface ResultsGridProps {
  matches: MatchResult[];
  queryFaces: number;
  loading: boolean;
  reportUrl: string | null;
}

const ResultsGrid = ({ matches, queryFaces, loading, reportUrl }: ResultsGridProps) => {
  return (
    <section className="results">
      {loading && <div className="results-state">Scanning your library…</div>}
      {!loading && !matches.length && (
        <div className="results-state">
          {queryFaces ? 'No matches yet. Try another angle or expand the dataset.' : 'Upload a face to see matches here.'}
        </div>
      )}

      {!loading && matches.length > 0 && (
        <>
          <div className="results-header">
            <h3>Matches</h3>
            <div className="results-tools">
              <span>
                {matches.length} photo{matches.length !== 1 ? 's' : ''}
              </span>
              {reportUrl && (
                <a className="download-report" href={reportUrl} target="_blank" rel="noreferrer">
                  Download report
                </a>
              )}
            </div>
          </div>
          <div className="grid">
            {matches.map((match) => (
              <article key={match.photo_id} className="match-card">
                <img src={match.media_url} alt={`Match ${match.photo_id}`} loading="lazy" />
                <div className="meta">
                  <span className="distance">
                    {typeof match.distance === 'number'
                      ? `Confidence: ${Math.max(0, 1 - match.distance).toFixed(2)}`
                      : 'Same person (cluster match)'}
                  </span>
                  {match.labels.length > 0 && <span className="labels">{match.labels.join(', ')}</span>}
                </div>
              </article>
            ))}
          </div>
        </>
      )}
    </section>
  );
};

export default ResultsGrid;
