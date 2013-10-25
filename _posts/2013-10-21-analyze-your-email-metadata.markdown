---
layout: post
title:  "Analyze your email metadata"
date:   2013-10-21
tags: [immersion, metadata, mozfest, tutorial]
---

##Downloading email headers
First, you need to be logged in to [Immersion](https://immersion.media.mit.edu)<sup>1</sup>. To download the email headers in JSON format, visit <a href="https://immersion.media.mit.edu/downloademails" target="_blank">immersion.media.mit.edu/downloademails</a>. If you are not logged in, you will be redirected to the login page. The filename is <code>allemails.json</code> and it contains the metadata of every email you have exchanged. A sample email entry from the JSON file is shown below. There will be many more such entries in the JSON file.

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
The first thing you want to do when analyzing data is to clean it. We will walk through a simple python script that parses your email headers and filters out the invalid ones<sup>2</sup>.
{% highlight python %}
import json
    
def filterEmails(emails):
  return [email for email in emails if email is not None and email['toField'] and email['fromField']]

f = open('/PATH_TO_JSON_FILE/allemails.json')
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

Now, from the sent and received statistics, we can easily obtain the set of *filtered email addresses*, which we will refer to as *collaborators* from now on:

{% highlight python %}
def getCollaborators(emails, K):
  sentCounter, rcvCounter = getSentRcvCounters(emails)
  return set([person for person in sentCounter if sentCounter[person] >= K and rcvCounter[person] >= K])
collaborators = getCollaborators(emails,5) # obtain the collaborators for K=5
{% endhighlight %}

This set (collaborators) will help us make sure that all future results that involve email addresses belong to collaborators, and not mailing lists or promotion lists.

##Analyzing the email metadata
At this point, we are ready to ask some interesting questions about our own metadata.

Let's find the most "private" collaborators, i.e. people with whom we have a high likelihood of exchanging a private (one to one) email without cc'ing anyone else. In other words, we want to construct a list of tuples, each tuple consisting of an email address and the probability of exchanging a private email, e.g. <code>('person@email.com',0.657)</code>. The probability is computed by dividing the number of private emails by the total number of exchanged emails with that person.

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

Let's print the top 20 private collaborators:
{% highlight python %}
for person, score in getPrivateContacts(emails, collaborators)[:20]:
  print person,'\t',score
print '-----------------'
{% endhighlight %}
It is easy to see that there is a problem :-). Exchanging 80 private emails out of 100 gives the same probability as exchanging 4 out of 5 (0.8). However, the second estimate is much more noisy that the first, i.e. it is not unlikely to get 4 heads out of 5 tosses of an unbiased coin and incorrectly estimate that there is 80% change of getting heads. To correct for this uncertainty, we will use [Wilson score interval][wilson-score] which gives a confidence interval around the estimated probability. The lower bound of the 99% confidence interval for 4/5 is 0.28 whereas for 80/100 is 0.68. This tells us that we are 99% confident that the actual probability is more than 0.28 for the 4/5 case, and more than 0.68 for the 80/100 case. Here is an implementation of the score interval. This code snippet must be inserted before the implementation of <code>getPrivateContacts</code>.

{% highlight python %}
from math import sqrt
def getLowerBound(pos, n):
  if n == 0: return 0
  phat = float(pos)/n
  z = 2.576 #1.96 is 95% confidence, 2.576 is 99% confidence
  return (phat + z*z/(2*n) - z * sqrt((phat*(1-phat)+z*z/(4*n))/n))/(1+z*z/n)
{% endhighlight %}

Now we can change the implementation of <code>getPrivateContacts</code> to account for this uncertainty by changing this line
{% highlight python %}
people = [(person, float(pvtCounter[person])/counter[person]) for person in pvtCounter if person in collaborators]
{% endhighlight %}

to this line

{% highlight python %}
people = [(person, getLowerBound(pvtCounter[person],counter[person])) for person in pvtCounter if person in collaborators]
{% endhighlight %}

Similarly, we can get the people with whom we have the most asymmetric relationship, i.e. we want to have a high likelihood of not getting an email back for every email we sent, and vice versa. To estimate this probability, we first need to identify the direction of the relationship. If it's an outgoing direction (we are sending more to person A than receiving), we want to estimate the probability of not receiving an email for every email we send, i.e. (#sent-#rcv) / #sent. Conversely, if we are receiving more emails than sending, we estimate the probability of not emailing back for every email we receive, i.e. (#rcv-#sent) / #rcv. We will again use the Wilson score interval to account for the uncertainty:

{% highlight python %}
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
{% endhighlight %}

Let's print the top 20 asymmetric collaborators:
{% highlight python %}
for person, score, direction in getAsymmetricContacts(emails, collaborators)[:20]:
  print person,'\t',score
print '-----------------'
{% endhighlight %}

We leave as an exercise for the reader to implement <code>getSymmetricContacts</code>, i.e. contacts with whom we have the most symmetric communication<sup>3</sup>.

You can find the entire python file [here](/static/simple-analysis.py).

<sup>
	3. <b>HINT</b> For an outgoing direction, compute the probability that we are going to receive back an email for every email we send. It should be obvious for an incoming direction at this point.
	<!-- <br/>4. Occasionally, I get emails that require my input, so I email back, and these sources satisfy the collaborator threshold. -->
</sup>


[wilson-score]: http://en.wikipedia.org/wiki/Binomial_proportion_confidence_interval#Wilson_score_interval

