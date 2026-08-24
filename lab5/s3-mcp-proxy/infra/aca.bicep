targetScope = 'resourceGroup'

@description('Azure region for the Container App resource.')
param location string = resourceGroup().location

@minLength(2)
@maxLength(32)
@description('Container App resource name.')
param containerAppName string

@description('Existing Container Apps managed environment resource ID.')
param containerAppsEnvironmentId string

@description('Built proxy image, including immutable tag or digest.')
param image string

@description('Existing user-assigned identity resource ID used to read Key Vault secrets.')
param keyVaultIdentityResourceId string

@description('Key Vault secret URI containing S3_MCP_API_KEY.')
param s3McpApiKeySecretUri string

@description('Key Vault secret URI containing a restricted AWS access key ID. PoC fallback only.')
param awsAccessKeyIdSecretUri string

@description('Key Vault secret URI containing the matching AWS secret access key. PoC fallback only.')
param awsSecretAccessKeySecretUri string

@description('Approved S3 bucket.')
param s3Bucket string

@description('Approved, non-empty S3 prefix.')
param s3Prefix string

@description('AWS region containing the bucket.')
param awsRegion string

@minValue(0)
param minReplicas int = 0

@minValue(1)
param maxReplicas int = 3

resource proxy 'Microsoft.App/containerApps@2025-02-02-preview' = {
  name: containerAppName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${keyVaultIdentityResourceId}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironmentId
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        allowInsecure: false
        targetPort: 8000
        transport: 'http'
      }
      secrets: [
        {
          name: 's3-mcp-api-key'
          keyVaultUrl: s3McpApiKeySecretUri
          identity: keyVaultIdentityResourceId
        }
        {
          name: 'aws-access-key-id'
          keyVaultUrl: awsAccessKeyIdSecretUri
          identity: keyVaultIdentityResourceId
        }
        {
          name: 'aws-secret-access-key'
          keyVaultUrl: awsSecretAccessKeySecretUri
          identity: keyVaultIdentityResourceId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 's3-mcp-proxy'
          image: image
          env: [
            {
              name: 'S3_BUCKET'
              value: s3Bucket
            }
            {
              name: 'S3_PREFIX'
              value: s3Prefix
            }
            {
              name: 'AWS_REGION'
              value: awsRegion
            }
            {
              name: 'S3_MCP_API_KEY'
              secretRef: 's3-mcp-api-key'
            }
            {
              name: 'AWS_ACCESS_KEY_ID'
              secretRef: 'aws-access-key-id'
            }
            {
              name: 'AWS_SECRET_ACCESS_KEY'
              secretRef: 'aws-secret-access-key'
            }
            {
              name: 'MCP_HOST'
              value: '0.0.0.0'
            }
            {
              name: 'MCP_PORT'
              value: '8000'
            }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/healthz'
                port: 8000
              }
              initialDelaySeconds: 10
              periodSeconds: 30
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/healthz'
                port: 8000
              }
              initialDelaySeconds: 5
              periodSeconds: 10
            }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
      }
    }
  }
}

output mcpEndpoint string = 'https://${proxy.properties.configuration.ingress.fqdn}/mcp'
output healthEndpoint string = 'https://${proxy.properties.configuration.ingress.fqdn}/healthz'
