SCHEME = NexusCorp
DESTINATION = platform=macOS,arch=arm64

# The Desktop is a File Provider volume: it re-injects com.apple.FinderInfo on
# freshly written directories, which ad-hoc codesign rejects with
# "resource fork, Finder information, or similar detritus not allowed".
# Keeping DerivedData off this volume avoids it.
DERIVED = $(HOME)/Library/Developer/NexusCorpDerivedData

.PHONY: generate build test run clean

generate:
	xcodegen generate

build: generate
	xcodebuild -project NexusCorp.xcodeproj -scheme $(SCHEME) -destination '$(DESTINATION)' -derivedDataPath $(DERIVED) build

test: generate
	xcodebuild -project NexusCorp.xcodeproj -scheme $(SCHEME) -destination '$(DESTINATION)' -derivedDataPath $(DERIVED) test

run: build
	open $(DERIVED)/Build/Products/Debug/NexusCorp.app

clean:
	rm -rf $(DERIVED)
