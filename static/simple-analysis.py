# sample email header in JSON format
{ 'fromField': ['Deepak Jagdish', 'deepak.jagdish@gmail.com'],
  'toField': [['Daniel Smilkov', 'dsmilkov@gmail.com']],
  'dateField': 1372743719,
  'isSent': False,
  'threadid': '1439426117975266137',
}

import json
    
def filterEmails(emails):
  return [email for email in emails if email is not None and email['toField'] and email['fromField']]

f = open('/Users/dsmilkov/Downloads/allemails.json')
emails = filterEmails(json.load(f))

from collections import Counter
def getSentRcvCounters(emails):
  sentCounter, rcvCounter = Counter(), Counter()
  for email in emails:
    if email['isSent']:
      for person in email['toField']:
        sentCounter[person[1]] += 1
    else:
      person = email['fromField']
      rcvCounter[person[1]] += 1
  return sentCounter, rcvCounter

def getCollaborators(emails, K):
  sentCounter, rcvCounter = getSentRcvCounters(emails)
  return set([person for person in sentCounter if sentCounter[person] >= K and rcvCounter[person] >= K])
collaborators = getCollaborators(emails,5) # obtain the collaborators for K=5

from math import sqrt
def getLowerBound(pos, n):
  if n == 0: return 0
  phat = float(pos)/n
  z = 2.576 #1.96 is 95% confidence, 2.576 is 99% confidence
  return (phat + z*z/(2*n) - z * sqrt((phat*(1-phat)+z*z/(4*n))/n))/(1+z*z/n)

def getPrivateContacts(emails, collaborators):
  ncoll = 0
  counter, pvtCounter = Counter(), Counter()
  for email in emails:
    if email is None: continue
    isPrivate = len(email['toField']) <= 1
    if email['isSent']:
      for person in email['toField']:
        counter[person[1]] += 1
        if isPrivate: pvtCounter[person[1]] += 1
    else:
      person = email['fromField']
      counter[person[1]] += 1
      if isPrivate: pvtCounter[person[1]] += 1
  people = [(person, getLowerBound(pvtCounter[person],counter[person])) for person in pvtCounter if person in collaborators]
  people.sort(key=lambda x: x[1], reverse=True)
  return people

for person, score in getPrivateContacts(emails, collaborators)[:20]:
  print person,'\t',score
print '-----------------'

def getAsymmetricContacts(emails, collaborators):
  sentCounter, rcvCounter = getSentRcvCounters(emails)
  people = []
  for person in sentCounter:
    if person not in collaborators: continue
    sent, rcv = sentCounter[person], rcvCounter[person]
    if (sent > rcv):
      people.append((person, getLowerBound(sent-rcv, sent), 'ME-->'))
    else:
      people.append((person, getLowerBound(rcv-sent, rcv), 'ME<--'))
  people.sort(key=lambda x: x[1], reverse=True)
  return people
  
for person, score, direction in getAsymmetricContacts(emails, collaborators)[:20]:
  print person, '\t', score, '\t', direction
print '-----------------'