---
layout: post
title:  "Analyze your email metadata"
date:   2013-10-21
tags: [immersion, metadata, mozfest, tutorial]
---

##Downloading email headers
First, you need to be logged in to Immersion<sup>1</sup>. To download the email headers in JSON format, visit http://immersion.media.mit.edu/downloademails. The filename is <code>allemails.json</code>. If you are not logged in, you will be redirected to the login page. Here is a sample email entry:


{% highlight python %}
{ 'fromField': ['Deepak Jagdish', 'email1@email.com'],
  'toField': [['Daniel Smilkov', 'email2@email.com'],['Cesar Hidalgo', 'email3@email.com']],
  'dateField': 1372743719,
  'isSent': False,
  'threadid': '1439426117975266137',
}
{% endhighlight %}


The <code>toField</code> contains both <code>TO</code> and <code>CC</code> entries.

<sup>1. Being logged in to Immersion means having a login cookie on your browser.
</sup>

##Cleaning the data
The first thing you want to do when analyzing data is to clean it. Here is a python code that reads all the emails and filters out the invalid ones<sup>2</sup>.
{% highlight python %}
import json
    
def filterEmails(emails):
  return [email for email in emails if email is not None and email['toField'] and email['fromField']]

f = open('/Users/dsmilkov/Downloads/allemails.json')
emails = filterEmails(json.load(f))
{% endhighlight %}
    
    
<sup>2. There are several things that can make an email invalid; missing  <code>FROM</code> or <code>TO</code> field, invalid timestamp, or simply being an empty object.
</sup>

Furthermore, we want to filter out anything that is a mailing list (e.g. company-wide lists, project based lists) or a promotion list (e.g. Facebook and LinkedIn updates). A simple but effective way to do is to keep email A if we have both sent and received at least K emails with A. To do this, we first count the number of sent and received emails for every email address. We will use <code>Counter</code>, a nice dictionary-based structure for counting:

{% highlight python %}
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
{% endhighlight %}

Now, from the sent and receive statistics, we can easily obtain the set of filtered email addresses, which at this point makes sense to refer to them as collaborators:

{% highlight python %}
def getCollaborators(emails, K):
  sentCounter, rcvCounter = getSentRcvCounters(emails)
  return set([person for person in sentCounter if sentCounter[person] >= K and rcvCounter[person] >= K])
{% endhighlight %}

This set will help us make sure that all future results that involve email addresses belong to collaborators, and not mailing lists or promotion lists.

##Analyzing the email metadata

Now, let's find the most "private" collaborators, i.e. people with whom we have a high likelihood of exchanging a private (one to one) email without cc'ing anyone else. In other words, we want to construct a list of tuples, each tuple consisting of an email address and the probability of exchanging a private email, e.g. <code>('email3@email.com',0.657)</code>. The probability is computed by dividing the number of private emails by the total number of exchanged emails.

{% highlight python %}
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
  people = [(person, float(pvtCounter[person])/counter[person]) for person in pvtCounter if person in collaborators]
  people.sort(key=lambda x: x[1], reverse=True)
  return people
{% endhighlight %}

There is a problem though. Exchanging 80 private emails out of 100 gives the same probability as exchanging 4 out of 5 (0.8). However, the second estimate is much more noisy that the first, i.e. it is not unlikely to get 4 private emails out of 5 even when the probability of a private email is only 0.4 instead of 0.8. To correct for this uncertainty, we will use [Wilson score interval][wilson-score] which gives a confidence interval around the estimated probability. The lower bound of the 99% confidence interval for 4/5 is 0.28 whereas for 80/100 is 0.68. This tells us that we are 99% confident that the actual probability is more than 0.28 for the 4/5 case, and more than 0.68 for the 80/100 case. Here is an implementation of the score interval:

{% highlight python %}   
from math import sqrt
def getLowerBound(pos, n):
  if n == 0: return 0
  phat = float(pos)/n
  z = 2.576 #1.96 is 95% confidence, 2.576 is 99% confidence
  return (phat + z*z/(2*n) - z * sqrt((phat*(1-phat)+z*z/(4*n))/n))/(1+z*z/n)
{% endhighlight %}

Now we can change the implementation for private collaborators to account for this uncertainty by changing the 3rd to last line to:

    people = [(person, getLowerBound(pvtCounter[person],counter[person])) for person in pvtCounter if person in collaborators]

To print the top 10 private collaborators, we can run <code>print getPrivateContacts(emails, collaborators)[:10]</code>.

Similarly, we can get the people with whom we have the most symmetric relationship, i.e. we want to have a high likelihood of getting an email back for every email we sent, and vice versa. To estimate this probability, we first need to identify the direction of the relationship, i.e. if we are sending more to person A than receiving, then it's an outgoing direction, and we want to estimate the probability of receiving an email for every email we send, i.e. # rcv / #sent. Conversely, if we are receiving more emails than sending, then it's an incoming direction, and we estimate the probability of sending back an email to person A, for every email we receive from him/her, i.e. #sent / #rcv. We will again use the Wilson score interval to account for the uncertainty:

{% highlight python %}
def getSymmetricContacts(emails, collaborators):
  sentCounter, rcvCounter = getSentRcvCounters(emails)
  people = []
  for person in sentCounter:
    if person not in collaborators: continue
    sent, rcv = sentCounter[person], rcvCounter[person]
    if (sent > rcv):
      people.append((person, getLowerBound(rcv, sent), 'ME-->'))
    else:
      people.append((person, getLowerBound(sent, rcv), 'ME<--'))
  people.sort(key=lambda x: x[1], reverse=True)
  return people
{% endhighlight %}

We leave as an exercise for the reader to implement <code>getAsymmetricContacts</code>, i.e. contacts with whom we have the most asymmetric communication<sup>3</sup>. In my case, these are usually administrative people that are sending mass emails to the lab<sup>4</sup> or maybe people that are spamming me, or me spamming them :).

<sup>
	3. <b>HINT</b> For an outgoing direction, compute the probability that we are not going to receive back an email for every email we send. It should be obvious for an incoming direction at this point.
	<br/>4. Occasionally, I get emails that require my input, so I email back, and these sources satisfy the collaborator threshold.
</sup>


[wilson-score]: http://en.wikipedia.org/wiki/Binomial_proportion_confidence_interval#Wilson_score_interval

