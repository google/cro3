// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"errors"
	"fmt"
)

// Node is a simple Double-Linked-List Node
type Node struct {
	Key  string
	Val  string
	next *Node
	prev *Node
}

// Deque is a simple local implementation of a Deque.
// This is required as this is not a built-in lib for golang (and none of the
// options currently do everything we need)
type Deque struct {
	size  int64
	front *Node
	back  *Node
}

func MakeDeque() *Deque {
	return &Deque{
		size:  0,
		front: nil,
		back:  nil,
	}
}

func (d *Deque) IsEmpty() bool {
	return d.size == 0
}

func (d *Deque) Size() int64 {
	return d.size
}

func (d *Deque) PushToFront(k, v string) *Node {
	if d.size == 0 {
		d.addEmpty(k, v)
	} else {
		d.front = &Node{
			Key:  k,
			Val:  v,
			next: d.front,
			prev: nil,
		}
		d.front.next.prev = d.front
	}
	d.size++
	return d.front
}

func (d *Deque) Pop(n *Node) (*Node, error) {
	if n == nil {
		return nil, errors.New("can't pop empty node")
	}
	if d.front.Key == n.Key {
		return d.PopFromFront()
	} else if d.back.Key == n.Key {
		return d.PopFromBack()
	} else {
		d.size--
		next := n.next
		prev := n.prev
		prev.next = next
		next.prev = prev
		return n, nil
	}
}

func (d *Deque) PopFromFront() (*Node, error) {
	if d.size == 0 {
		return nil, errors.New("can't pop from empty deque")
	} else if d.size == 1 {
		d.size--
		return d.removeFinal(), nil
	} else {
		d.size--
		n := d.front
		d.front = d.front.next
		d.front.prev = nil
		return n, nil
	}
}

func (d *Deque) PopFromBack() (*Node, error) {
	if d.size == 0 {
		return nil, errors.New("can't pop from empty deque")
	} else if d.size == 1 {
		d.size--
		return d.removeFinal(), nil
	} else {
		d.size--
		n := d.back
		d.back = d.back.prev
		d.back.next = nil
		return n, nil
	}
}

func (d *Deque) PushToBack(k, v string) *Node {
	if d.size == 0 {
		d.addEmpty(k, v)
	} else {
		d.back = &Node{
			Key:  k,
			Val:  v,
			next: nil,
			prev: d.back,
		}
		d.back.prev.next = d.back
	}
	d.size++
	return d.back
}

func (d *Deque) addEmpty(k, v string) {
	d.front = &Node{
		Key:  k,
		Val:  v,
		next: nil,
		prev: nil,
	}
	d.back = d.front
}

func (d *Deque) removeFinal() *Node {
	n := d.front
	d.front = nil
	d.back = nil
	return n
}

// LRU is a least recently used cache for KVs
// TODO(jaquesc) synchronize (i.e.: Add locks)
type LRU struct {
	maxSize          int64
	deletionCallBack func(string, string)
	deque            *Deque
	hashMap          map[string]*Node
}

func MakeLRU(maxSize int64, cb func(string, string)) (*LRU, error) {
	if maxSize <= 1 {
		return nil, errors.New("maxSize must be > 1")
	}
	return &LRU{
		maxSize:          maxSize,
		deletionCallBack: cb,
		deque:            MakeDeque(),
		hashMap:          map[string]*Node{},
	}, nil
}

func (l *LRU) Add(key, val string) error {
	n := l.deque.PushToBack(key, val)
	l.hashMap[key] = n

	// If exceeds max size we remove the last used
	if l.deque.size > l.maxSize {
		r, err := l.deque.PopFromFront()
		if err != nil {
			return err
		}
		l.deletionCallBack(r.Key, r.Val)
		delete(l.hashMap, r.Key)
	}

	return nil
}

func (l *LRU) Get(key string) (string, error) {
	if !l.Exists(key) {
		return "", fmt.Errorf("key does not exist, %s", key)
	}

	n := l.hashMap[key]
	val := n.Val

	// Update last used
	l.deque.Pop(n)
	l.deque.PushToBack(n.Key, n.Val)

	return val, nil
}

func (l *LRU) Exists(key string) bool {
	_, ok := l.hashMap[key]
	return ok
}

func (l *LRU) Delete() {
	for key, n := range l.hashMap {
		l.deletionCallBack(key, n.Val)
	}
}
