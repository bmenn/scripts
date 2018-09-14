import requests
import argparse
import json
import pandas as pd
import time
import sys


def search(query):
    API_SEARCH = 'https://www.semanticscholar.org/api/1/search'
    body = {'authors': [],
            'coAuthors': [],
            'enableEntities': True,
            'enableRefinements': False,
            'entities': [],
            'facets': {},
            'pageSize': 100,
            'publicationTypes': [],
            'queryString': '',
            'requireViewablePdf': False,
            'sort': 'relevance',
            'venues': [],
            'yearFilter': None}
    body.update(query)

    num_pages = 1
    page = 1
    search_results = []
    while page <= num_pages:
        body['page'] = page
        response = requests.post(API_SEARCH,
                                 json=body)
        response.raise_for_status()

        content = json.loads(response.content)
        search_results.extend(content['results'])
        num_pages = content['totalPages']
        page += 1
        time.sleep(0.5)
        print('%d/%d' % (page - 1, num_pages),
              file=sys.stderr)

    return search_results


def paper_lookup(paper_id):
    response = requests.get(
        'http://api.semanticscholar.org/v1/paper/{id}'.format(id=paper_id))

    response.raise_for_status()

    return json.loads(response.content)['citations']

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Find papers cited listed DOIs')

    parser.add_argument('--paper', action='append', metavar='paper_id',
                        default=[], nargs=1)
    parser.add_argument('--query', action='append', metavar='query_json',
                        default=[], nargs=1)

    args = parser.parse_args()
    papers = [e for l in args.paper for e in l]
    queries = [e for l in args.query for e in l]
    results = []
    citation_dois = []
    citation_s2id = []

    for paper in papers:
        paper_citations = paper_lookup(paper)
        results.extend(paper_citations)
        # citation_dois.append(set([e['doi'] for e in paper_citations]))
        citation_s2id.append(set([e['paperId'] for e in paper_citations]))

    for query in queries:
        query_results = search(json.loads(query))

        results.extend(query_results)
        citation_s2id.append(set([e['id'] for e in query_results]))

    # dois_intersection = set.intersection(*citation_dois)
    s2id_intersection = set.intersection(*citation_s2id)

    df = pd.DataFrame([
        doc
        for doc in results
        if ('paperId' in doc and doc['paperId'] in s2id_intersection)
            or ('id' in doc and doc['id'] in s2id_intersection)])

    empty_paper_id = pd.isnull(df['paperId'])
    if 'id' in df.columns:
        df[empty_paper_id]['paperId'] = df[empty_paper_id]['id']
        df = df.drop(['id'], axis=1)
    df = df.drop_duplicates(subset=['paperId'])

    print(df.to_csv())
